"""The prompt eval (feature 16). Run by hand against the real model: `make eval`.

It is not part of the app and the app never imports it. It calls the same pure functions the
app's services call (`analyze()` and `tailor()`), scores the output with the guardrail and
keyword coverage functions, and never opens a database session.
"""
