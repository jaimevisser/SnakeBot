import logging
import time
from datetime import datetime

import snakebot

_log = logging.getLogger(__name__)

class TicketAlreadyExistsError(Exception):
    """Raised when a user tries to create a ticket but already has one"""
    def __init__(self, user_id, ticket):
        self.user_id = user_id
        self.ticket = ticket
        super().__init__(f"User {user_id} already has an open ticket")

class TicketManager:
    def __init__(self, bot, question_manager):
        self.bot = bot
        self.question_manager = question_manager
        # Initialize store with an empty list - tickets will be stored as dicts in this list
        self.store = snakebot.Store("data/tickets.json", [])
    
    def create_ticket(self, user_id):
        existing_ticket = self.get_user_ticket(user_id)
        if existing_ticket:
            _log.info(f"User {user_id} already has an open ticket, raising exception")
            raise TicketAlreadyExistsError(user_id, existing_ticket)
            
        # Create ticket with user ID and current timestamp
        timestamp = int(time.time())
        
        ticket = {
            "user_id": user_id,
            "created_at": timestamp,
            "status": "open"
        }
        
        # Add the ticket to the store
        self.store.data.append(ticket)
        
        # Save changes to disk
        self.save
        
        _log.info(f"Created ticket for user {user_id} at timestamp {timestamp}")
        return ticket
        
    def get_ticket_position(self, user_id):
        position = 0
        user_ticket = None
        
        for ticket in self.store.data:
            if ticket.get('status') == 'open':
                if ticket.get('user_id') == user_id:
                    # Found the user's ticket
                    user_ticket = ticket
                    break
                else:
                    # This is another open ticket before the user's ticket
                    position += 1
        
        # If no ticket found, return None and -1
        if not user_ticket:
            return None, -1
        
        _log.info(f"User {user_id} ticket is at position {position} in queue")
        return user_ticket, position
        
    def get_user_ticket(self, user_id):
        for ticket in self.store.data:
            if ticket.get('user_id') == user_id and ticket.get('status') == 'open':
                _log.info(f"Found open ticket for user {user_id}")
                return ticket
        
        # If we get here, no open ticket was found
        _log.info(f"No open ticket found for user {user_id}")
        return None
    
    def remove_ticket(self, user_id):
        ticket = self.get_user_ticket(user_id)
        if not ticket:
            return False
        self.store.data = [t for t in self.store.data if t is not ticket]
        self.save()
        _log.info(f"Removed ticket for user {user_id}")
        return True
    
    def save(self):
        """Save the current state of tickets to disk"""
        self.store.sync()