from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_REPORT_TYPE = auto()
    AWAITING_MESSAGE = auto()
    AWAITING_USER = auto()
    MESSAGE_IDENTIFIED = auto()
    USER_IDENTIFIED = auto()
    AWAITING_ABUSE_TYPE = auto()
    AWAITING_BLOCK_DECISION = auto()
    REPORT_COMPLETE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    MESSAGE_KEYWORD = "message"
    CONVERSATION_KEYWORD = "conversation"
    USER_KEYWORD = "user"
    ABUSE_TYPES_DICT = {
        "1": "harassment or bullying",
        "2": "nudity or pornography",
        "3": "suicide or self-harm",
        "4": "violence or drug abuse",
        "5": "the user may be under 13",
        "6": "selling or promoting restricted items",
        "7": "misleading content or scams",
        "8": "threatening or blackmailing",
        "9": "impersonation"
    }

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        # User cancels report.
        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        # User starts reporting process.
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Are you reporting a message, a user, or a conversation?\n"
            reply += "You can say `" + self.MESSAGE_KEYWORD + "`, `" + self.USER_KEYWORD + "`, or `" + self.CONVERSATION_KEYWORD + "`."
            self.state = State.AWAITING_REPORT_TYPE
            return [reply]
        
        # User specifies what they're reporting (message, user, conversation).
        if self.state == State.AWAITING_REPORT_TYPE:
            match message.content.lower():
                case self.MESSAGE_KEYWORD:
                    reply = "Please copy and paste the link to the message you want to report.\n"
                    reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
                    self.state = State.AWAITING_MESSAGE
                    return [reply]
                case self.USER_KEYWORD:
                    reply = "Please copy and paste the ID of the user profile you wish to report.\n"
                    reply += "You can obtain this ID by turning on Developer Mode, right-clicking the user's name or profile picture, and clicking `Copy User ID`."
                    self.state = State.AWAITING_USER
                    return [reply]
                case self.CONVERSATION_KEYWORD:
                    reply = "Not implemented yet."
                    return [reply]
                case _:
                    reply = "That is not a valid response. Please say `" + self.MESSAGE_KEYWORD + "`, `" + self.USER_KEYWORD + "`, or `" + self.CONVERSATION_KEYWORD + "`, or say `" + self.CANCEL_KEYWORD + "` to cancel."
                    self.state = State.AWAITING_REPORT_TYPE
                    return [reply]
        
        # User is reporting a message.
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('^(?:https:\/\/discord.com\/channels)\/(\d+)\/(\d+)\/(\d+)', message.content)
            if not m:
                reply = "I'm sorry, I couldn't read that link. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                return [reply]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from servers that I'm not in. Please have the server owner add me to the server and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                reply = "It seems this channel was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                return [reply]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                reply = "It seems that this message was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                return [reply]

            # Here we've found the message.
            self.state = State.MESSAGE_IDENTIFIED
            reply = "I found this message:" + "```" + message.author.name + ": " + message.content + "```\n"
            reply += "What are you reporting this message for? Enter the number for the type of abuse from the list below. \n\n"
            for key, value in self.ABUSE_TYPES_DICT.items():
                reply += "\n" + key + ". " + value
            self.state = State.AWAITING_ABUSE_TYPE
            return [reply]
        
        # User is reporting a user profile.
        if self.state == State.AWAITING_USER:
            try:
                user = await self.client.fetch_user(message.content)
            except discord.errors.NotFound:
                reply = "It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                return [reply]
            
            # Here we've found the user.
            self.state = State.USER_IDENTIFIED
            reply = "What are you reporting " + user.name + " for? Enter the number for the type of abuse from the list below.\n"
            for key, value in self.ABUSE_TYPES_DICT.items():
                reply += "\n" + key + ". " + value
            self.state = State.AWAITING_ABUSE_TYPE
            return [reply]            
        
        # User specifies the abuse type.
        if self.state == State.AWAITING_ABUSE_TYPE:
            # Other abuse type. Shallow implementation.
            if message.content.lower() in self.ABUSE_TYPES_DICT.keys() and self.ABUSE_TYPES_DICT[message.content] != "impersonation":
                reply = "Thank you for your report with the listed reason of `" + self.ABUSE_TYPES_DICT[message.content]+ "`.\n\n"
                reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                reply += "Would you also like to block this user? Enter `yes` or `no`."
                self.state = State.AWAITING_BLOCK_DECISION
            # Impersonation
            elif message.content.lower() in self.ABUSE_TYPES_DICT.keys() and self.ABUSE_TYPES_DICT[message.content] == "impersonation":
                reply = "Not implemented yet."
            else:
                reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User decides whether to also block the user profile they are reporting.
        if self.state == State. AWAITING_BLOCK_DECISION:
            match message.content.lower():
                case "yes":
                    reply = "Not implemented yet."
                    self.state = State.REPORT_COMPLETE
                case "no":
                    reply = "Ok."
                    self.state = State.REPORT_COMPLETE
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                    self.state = State.AWAITING_BLOCK_DECISION
            return [reply]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    

