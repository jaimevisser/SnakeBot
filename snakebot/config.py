import yaml

class Config:
    def __init__(self):
        with open('data/bot.token', 'r') as file:
            self.token = file.read().strip()
        with open('data/config.yaml', 'r') as file:
            config = yaml.safe_load(file)
        self.channel_id = config.get('channel_id')
        self.player_questions = config.get('player_questions', [])
        self.text = config.get('bot_text', {})
