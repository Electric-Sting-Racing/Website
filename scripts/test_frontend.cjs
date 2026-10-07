/* Dependency-free behavior tests. These do not replace browser layout tests. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../static/js/site-v5.js'), 'utf8');

class Target {
  constructor() { this.listeners = {}; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  emit(name, event = {}) { for (const callback of this.listeners[name] || []) callback(event); }
}
class Element extends Target {
  constructor(top = 0) {
    super();
    this.classes = new Set(); this.attrs = {}; this.children = []; this.top = top;
    this.classList = {
      add: (...names) => names.forEach(name => this.classes.add(name)),
      remove: (...names) => names.forEach(name => this.classes.delete(name)),
      contains: name => this.classes.has(name),
      toggle: (name, force) => {
        const value = force === undefined ? !this.classes.has(name) : force;
        if (value) this.classes.add(name); else this.classes.delete(name);
        return value;
      },
    };
    this.styles = {};
    this.style = { setProperty: (name, value) => { this.styles[name] = value; } };
  }
  append(child) { child.parentElement = this; this.children.push(child); }
  contains(child) { return this === child || this.children.some(item => item.contains(child)); }
  matches(selector) { return selector.split(', ').some(part => this.classes.has(part.slice(1))); }
  closest(selector) { return this.tag === selector ? this : this.parentElement?.closest(selector); }
  setAttribute(name, value) { this.attrs[name] = value; }
  getAttribute(name) { return this.attrs[name]; }
  getBoundingClientRect() { return { top: this.top }; }
  focus() { this.focused = true; }
}

function setup(options = {}) {
  const doc = new Target(), win = new Target();
  const header = new Element(), toggle = new Element(), nav = new Element(), label = new Element(), link = new Element();
  header.append(toggle); header.append(nav); nav.append(link); link.tag = 'a';
  toggle.setAttribute('aria-expanded', 'false');
  const grid = new Element(); grid.classList.add('member-grid');
  const items = [new Element(100), new Element(1000), new Element(1400)];
  items.forEach(item => grid.append(item));
  const child = new Element(); items[2].append(child);
  const selectors = { '[data-menu-toggle]': toggle, '[data-nav]': nav, '[data-header]': header, '[data-menu-label]': label };
  doc.querySelector = selector => selectors[selector];
  doc.querySelectorAll = () => items;
  doc.documentElement = new Element();
  doc.getElementById = id => id === 'section' ? items[2] : null;
  const mobile = new Target(), motion = new Target(); motion.matches = !!options.reduced;
  win.matchMedia = query => query.includes('reduced') ? motion : mobile;
  win.innerHeight = 800;
  win.location = { hash: options.hash || '' };
  const observers = [];
  class Observer {
    constructor(callback, settings) {
      if (options.constructorFails) throw new Error('Observer unavailable');
      this.callback = callback; this.settings = settings; this.observed = new Set(); observers.push(this);
    }
    observe(item) {
      if (options.observeFails) throw new Error('Observation failed');
      this.observed.add(item);
    }
    unobserve(item) { this.observed.delete(item); }
    disconnect() { this.disconnected = true; this.observed.clear(); }
  }
  if (!options.noObserver) win.IntersectionObserver = Observer;
  vm.runInNewContext(source, { document: doc, window: win, Element, IntersectionObserver: Observer });
  return { doc, win, items, child, observers, toggle, nav, label, link, mobile, motion };
}
const pending = item => item.classList.contains('is-pending');

test('above-fold content stays visible; below-fold cards are observed and staggered', () => {
  const state = setup();
  assert.equal(pending(state.items[0]), false);
  assert.equal(pending(state.items[1]), true);
  assert.equal(state.items[1].styles['--reveal-delay'], '70ms');
  assert.equal(state.observers[0].observed.size, 2);
});
test('each card reveals once on intersection, not before', () => {
  const { items, observers: [observer] } = setup();
  observer.callback([{ target: items[1], isIntersecting: false }]);
  assert.equal(pending(items[1]), true);
  observer.callback([{ target: items[1], isIntersecting: true }]);
  assert.equal(pending(items[1]), false);
  assert.equal(observer.observed.has(items[1]), false);
  assert.equal(pending(items[2]), true);
});
for (const mode of ['noObserver', 'constructorFails', 'observeFails', 'reduced']) {
  test(`${mode}: all content remains readable`, () => {
    const { items } = setup({ [mode]: true });
    assert.equal(items.some(pending), false);
    assert.equal(items.every(item => item.classList.contains('is-visible')), true);
  });
}
test('changing reduced-motion preference reveals remaining content', () => {
  const { items, motion, observers: [observer] } = setup();
  motion.emit('change', { matches: true });
  assert.equal(items.some(pending), false);
  assert.equal(observer.disconnected, true);
});
test('keyboard focus reveals the enclosing card', () => {
  const { doc, child, items } = setup();
  doc.emit('focusin', { target: child });
  assert.equal(pending(items[2]), false);
});
test('initial and changed section fragments reveal their content', () => {
  assert.equal(pending(setup({ hash: '#section' }).items[2]), false);
  const { win, items } = setup();
  win.location.hash = '#section'; win.emit('hashchange');
  assert.equal(pending(items[2]), false);
  assert.doesNotThrow(() => setup({ hash: '#%ZZ' }));
});
test('printing and back-forward restoration do not leave content hidden', () => {
  for (const name of ['beforeprint', 'pageshow']) {
    const { win, items } = setup(); win.emit(name, { persisted: true });
    assert.equal(items.some(pending), false);
  }
});
test('mobile toggle updates state and accessible label; Escape restores focus', () => {
  const { toggle, nav, label, doc } = setup();
  toggle.emit('click');
  assert.equal(nav.classList.contains('is-open'), true);
  assert.equal(toggle.getAttribute('aria-expanded'), 'true');
  assert.equal(label.textContent, 'Close navigation');
  doc.emit('keydown', { key: 'Escape' });
  assert.equal(nav.classList.contains('is-open'), false);
  assert.equal(toggle.getAttribute('aria-expanded'), 'false');
  assert.equal(label.textContent, 'Open navigation');
  assert.equal(toggle.focused, true);
});
test('navigation closes on link, outside click, outside focus, and breakpoint change', () => {
  for (const action of ['link', 'outside', 'focus', 'breakpoint']) {
    const { doc, toggle, nav, link, mobile } = setup(); toggle.emit('click');
    if (action === 'link') nav.emit('click', { target: link });
    if (action === 'outside') doc.emit('click', { target: new Element() });
    if (action === 'focus') doc.emit('focusin', { target: new Element() });
    if (action === 'breakpoint') mobile.emit('change');
    assert.equal(nav.classList.contains('is-open'), false, action);
  }
});
