class ConversationMemory:

    def __init__(self):
        self.history = []

    def add(self, role, message):

        self.history.append({
            "role": role,
            "message": message
        })

    def recent(self, limit=6):

        return self.history[-limit:]