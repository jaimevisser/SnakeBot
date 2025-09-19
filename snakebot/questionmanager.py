import discord
import logging
from snakebot.ticketmanager import TicketManager

_log = logging.getLogger(__name__)

class QuestionManager:
    
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.get_ticket = None
        self.save_tickets = None
        
    def next_question_for_user(self, user_id):
        questions = self.config.player_questions
        if not questions:
            return None
        ids = [q['id'] for q in questions]
        
        user_ticket = self.get_ticket(user_id)
        if not user_ticket:
            return None
        if 'answers' not in user_ticket:
            user_ticket['answers'] = {}
            
        answered_ids = list(user_ticket['answers'].keys())
        unanswered_ids = [qid for qid in ids if qid not in answered_ids]
        if not unanswered_ids:
            return None
        next_question_id = unanswered_ids[0]
        return next((q for q in questions if q['id'] == next_question_id), None)

    async def ask_next_question(self, user_id):     
        next_question = self.next_question_for_user(user_id)
        if not next_question:
            _log.info(f"All questions answered for user {user_id}")
            return None
        
        if next_question['type'] == 'open':
            await self.open_question(user_id, next_question)
        elif next_question['type'] == 'single_choice':
            await self.single_choice_question(user_id, next_question)
        elif next_question['type'] == 'multiple_choice':
            await self.multiple_choice_question(user_id, next_question)
        
    async def open_question(self, user_id, question):
        channel = await self.get_dm_channel(user_id)
        await channel.send(question['message']+self.config.text["open_question"])
        
    async def single_choice_question(self, user_id, question):
        channel = await self.get_dm_channel(user_id)
        view = discord.ui.View()
        for option in question['options']:
            view.add_item(discord.ui.Button(
                label=option,
                style=discord.ButtonStyle.primary,
                custom_id=f"single_{question['id']}_{option}"
            ))
        await channel.send(question["message"]+self.config.text["single_choice"], view=view)
        
    async def multiple_choice_question(self, user_id, question):
        channel = await self.get_dm_channel(user_id)
        view = discord.ui.View()
        for option in question['options']:
            view.add_item(discord.ui.Button(
                label=option,
                style=discord.ButtonStyle.danger,
                custom_id=f"multi_{question['id']}_{option}"
            ))
        min_choices = question.get('min_choices', 1)
        if min_choices == 0:
            view.add_item(discord.ui.Button(
                label="skip",
                style=discord.ButtonStyle.secondary,
                custom_id=f"multi_{question['id']}_done"
            ))
        await channel.send(question['message']+self.config.text["multiple_choice"], view=view)
        
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get('custom_id')
        if not custom_id:
            return
        user_id = str(interaction.user.id)
        ticket = self.get_ticket(user_id)
        if not ticket:
            return
        if 'answers' not in ticket:
            ticket['answers'] = {}
        # Single choice
        if custom_id.startswith('single_'):
            parts = custom_id.split('_', 2)
            if len(parts) < 3:
                return
            _, qid, option = parts
            ticket['answers'][qid] = option
            self.save_tickets()
            await interaction.response.edit_message(content=f"Selected: {option}", view=None)
            await self.ask_next_question(user_id)
            return
        # Multiple choice
        if custom_id.startswith('multi_'):
            parts = custom_id.split('_', 2)
            if len(parts) < 3:
                return
            _, qid, rest = parts
            question = next((q for q in self.config.player_questions if q['id'] == qid), None)
            if not question:
                return
            min_choices = question.get('min_choices', 1)
            max_choices = question.get('max_choices', len(question['options']))
            # Track selected options in the message state
            selected = set()
            # Try to get current selected from message components
            for row in interaction.message.components:
                for btn in row.children:
                    if btn.style == discord.ButtonStyle.success and btn.custom_id.startswith(f"multi_{qid}_"):
                        val = btn.custom_id[len(f"multi_{qid}_"):]
                        if val not in ("next", "done"):
                            selected.add(val)
            # Toggle logic
            if rest not in ("next", "done"):
                if rest in selected:
                    selected.remove(rest)
                else:
                    if len(selected) < max_choices:
                        selected.add(rest)
            # Build new view
            view = discord.ui.View()
            for option in question['options']:
                style = discord.ButtonStyle.success if option in selected else discord.ButtonStyle.danger
                view.add_item(discord.ui.Button(
                    label=option,
                    style=style,
                    custom_id=f"multi_{qid}_{option}"
                ))
            # Add next/skip logic
            if len(selected) >= min_choices:
                view.add_item(discord.ui.Button(
                    label="next",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"multi_{qid}_next"
                ))
            elif min_choices == 0 and not selected:
                view.add_item(discord.ui.Button(
                    label="skip",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"multi_{qid}_done"
                ))
            # If next or skip pressed, save and advance
            if rest in ("next", "done"):
                ticket['answers'][qid] = list(selected)
                self.save_tickets()
                await interaction.response.edit_message(content=f"Selected: {', '.join(selected) if selected else 'None'}", view=None)
                await self.ask_next_question(user_id)
                return
            # Otherwise just update the view
            await interaction.response.edit_message(view=view)
    
    async def on_message(self, message): 
        user_id = str(message.author.id)
        question = self.next_question_for_user(user_id)
        if not question or question['type'] != 'open':
            return
        
        ticket = self.get_ticket(user_id)
        if not ticket:
            return
        if 'answers' not in ticket:
            ticket['answers'] = {}
        ticket['answers'][question['id']] = message.content
        self.save_tickets()
        await self.ask_next_question(user_id)
    
    async def get_dm_channel(self, user_id):
        user = await self.bot.fetch_user(int(user_id))
        return await user.create_dm()