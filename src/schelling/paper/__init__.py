"""Paper support (Session 14): deterministic evidence + figure generation for the write-up.

Nothing here writes prose. ``evidence`` regenerates every number the paper cites straight from the
repo's own artifacts (committed records, the DEU data pinned by SHA-256, the fixtures) so the
evidence table can be regenerated and diffed forever — no number is ever hand-typed. ``figures``
renders byte-stable SVGs from the same computed artifacts.
"""
