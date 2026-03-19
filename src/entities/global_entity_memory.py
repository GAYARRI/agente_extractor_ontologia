class GlobalEntityMemory:

    def __init__(self):
        self.counts = {}

    def update(self, entities):

        for e in entities:
            name = e["entity"].lower()
            self.counts[name] = self.counts.get(name, 0) + 1

    def get_counts(self):
        return self.counts