REGIONS = {
    "spain": {
        "providers": ["aerolineas", "level"],
        "date_range": ("2026-01-01", "2026-06-30"),
        "thresholds": {"store": 1200, "notify": 900, "one_way": 400},
        "destinations": ["MAD", "BCN"]  # Add more as needed
    },
    "australia": {
        "providers": ["level"],
        "date_range": ("2025-10-01", "2026-01-31"),
        "thresholds": {"store": 1800, "notify": 1500, "one_way": 800},
        "destinations": ["SYD", "MEL"]  # Add more as needed
    }
}
