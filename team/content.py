"""Small, code-owned content blocks that should remain stable across handoffs.

Editorial content belongs in Django models. These short program blocks are
structural copy: keeping them in one module makes the templates easier to
scan and the annual handoff easier to update.
"""

PROGRAM_PHASES = (
    {
        "season": "SPRING 2026",
        "label": "LAUNCH",
        "description": "Introduce Electric Sting to campus and build the first cross-disciplinary team.",
    },
    {
        "season": "SUMMER 2026",
        "label": "ORGANIZE",
        "description": "Grow the team, establish subteams, and turn a big idea into a buildable program.",
    },
    {
        "season": "FALL 2026",
        "label": "DESIGN",
        "description": "Complete subsystem design, source materials, and prepare the car for manufacturing.",
    },
    {
        "season": "SPRING 2027",
        "label": "BUILD + TEST",
        "description": "Manufacture, integrate, and test the vehicle as one cohesive system.",
    },
    {
        "season": "SUMMER 2027",
        "label": "COMPETE",
        "description": "Bring Electric Sting to Formula SAE Electric at Michigan International Speedway.",
    },
)

ENGINEERING_SYSTEMS = (
    ("01", "High Voltage", "Accumulator design, high-voltage distribution, and electrical safety."),
    ("02", "Powertrain", "Motor, inverter, drivetrain, and the systems that turn electrical energy into motion."),
    ("03", "Low Voltage/Controls", "Wiring harnesses, sensors, embedded software, and vehicle control systems."),
    ("04", "Frame", "Chassis structure, packaging, mounting points, and fabrication planning."),
    ("05", "Suspension", "Suspension geometry, steering, wheel assemblies, and vehicle dynamics."),
)

PROGRAM_METRICS = (
    ("01", "first", "FSAE EV team at Sacramento State"),
    ("20+", "students", "at our first team meeting"),
    ("06", "sections", "working toward one car"),
    ("2027", "finish line", "Formula SAE Electric"),
)

FEATURED_GALLERY_IMAGES = (
    {
        "image_path": "images/team-trackside.webp",
        "width": 1024,
        "height": 769,
        "srcset_paths": (("images/team-trackside-800.webp", 800), ("images/team-trackside.webp", 1024)),
        "sizes": "(max-width: 580px) 100vw, (max-width: 1050px) 50vw, 620px",
        "title": "Together at the track",
        "caption": "Electric Sting Racing team members spending time together trackside.",
        "alt_text": "Five Electric Sting Racing team members outdoors beside a racetrack under a blue sky.",
    },
    {
        "image_path": "images/team-launch.webp",
        "width": 2048,
        "height": 1536,
        "srcset_paths": (
            ("images/team-launch-800.webp", 800),
            ("images/team-launch-1280.webp", 1280),
            ("images/team-launch.webp", 2048),
        ),
        "sizes": "(max-width: 580px) 100vw, (max-width: 1050px) 50vw, 620px",
        "title": "The first team meeting",
        "caption": "A room full of students, questions, and the energy to build something new.",
        "alt_text": "Electric Sting Racing members gathered in a classroom during a team meeting.",
    },
    {
        "image_path": "images/team-outreach.webp",
        "width": 2048,
        "height": 1536,
        "srcset_paths": (
            ("images/team-outreach-800.webp", 800),
            ("images/team-outreach-1280.webp", 1280),
            ("images/team-outreach.webp", 2048),
        ),
        "sizes": "(max-width: 580px) 100vw, 1260px",
        "title": "Learning in public",
        "caption": "The work starts with sharing the plan, asking better questions, and bringing people in.",
        "alt_text": "Electric Sting Racing students gathered outside for a team presentation.",
    },
)
