"""Shareable single-page briefs for a graded question (Session 56, D56).

``schelling brief build <question-id>`` renders ``docs/briefs/<slug>.html`` — the approved
``first-graded-forecast.html`` design, but with EVERY figure computed from the committed artifacts
(the grading file, the ledger's GRADED block, the rubric's ``outcome_map``), never copied from the
reference. Prose lives in a committed per-question ``docs/briefs/<slug>.md`` with ``{{tags}}`` for
figures, resolved at build behind the same hard wall as the dossier: an unresolved tag fails the
build. The continuum chart is generated (marks from each forecast's value, axis scaled to the
spread), byte-identical on re-run. Refuses to run on an ungraded question.
"""
