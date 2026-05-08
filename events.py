import json
import os

class EventManager:
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as file:
                json.dump({}, file)
        self.pull_events()

    def pull_events(self):
        with open(self.filename, 'r') as file:
            self.events = json.load(file)

    def save_events(self):
        with open(self.filename, 'w') as file:
            json.dump(self.events, file, indent=4)

    def add_event(self, guild_id, name, channel, role, message):
        self.pull_events()
        guild_id = str(guild_id)
        if guild_id not in self.events:
            self.events[guild_id] = {}
        self.events[guild_id][name] = {"channel": channel, "role": role, "message": message}
        self.save_events()

    def remove_event(self, guild_id, name):
        self.pull_events()
        guild_id = str(guild_id)
        if guild_id not in self.events:
            return None
        if name not in self.events[guild_id]:
            return None
        del self.events[guild_id][name]
        self.save_events()

    def get_event(self, guild_id, name):
        self.pull_events()
        guild_id = str(guild_id)
        return self.events.get(guild_id, {}).get(name, None)
    
    def list_events(self, guild_id):
        self.pull_events()
        guild_id = str(guild_id)
        return [event for event in self.events.get(guild_id, {})]

class UserManager:
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as file:
                json.dump({}, file)
        self.pull_users()

    def pull_users(self):
        with open(self.filename, 'r') as file:
            self.users = json.load(file)

    def save_users(self):
        with open(self.filename, 'w') as file:
            json.dump(self.users, file, indent=4)

    def add_user(self, user, email):
        self.pull_users()
        user = str(user)
        self.users[user] = {"email": email}
        print(self.users)
        self.save_users()