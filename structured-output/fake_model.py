class FakeModel:
    """A scripted 'model': returns the prepared answers in order and records what it was asked."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, messages):
        self.calls.append([dict(m) for m in messages])
        return self.answers[len(self.calls) - 1]
