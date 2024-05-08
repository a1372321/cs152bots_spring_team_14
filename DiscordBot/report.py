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
    AWAITING_IMPERSONATION_VICTIM = auto()
    AWAITING_HAS_INSTAGRAM_PROFILE = auto()
    AWAITING_IMPERSONATING_REAL_PERSON = auto()
    AWAITING_REAL_INSTAGRAM_PROFILE = auto()
    AWAITING_REAL_INSTAGRAM_PROFILE_CONFIRM = auto()
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
    IMPERSONATION_VICTIM_DICT = {
        "1": "me",
        "2": "someone I know",
        "3": "someone else"
    }
    REPORT_INFO_DICT = {}

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
            reply += "Say `" + self.HELP_KEYWORD + "` at any time for more information.\n\n"
            reply += "Are you reporting a message, a user, or a conversation?\n"
            reply += "You can say `" + self.MESSAGE_KEYWORD + "`, `" + self.USER_KEYWORD + "`, or `" + self.CONVERSATION_KEYWORD + "`."
            self.state = State.AWAITING_REPORT_TYPE
            return [reply]
        
        # User specifies what they're reporting (message, user, conversation).
        if self.state == State.AWAITING_REPORT_TYPE:
            match message.content.lower():
                case self.MESSAGE_KEYWORD:
                    self.REPORT_INFO_DICT["Reporting"] = self.MESSAGE_KEYWORD
                    reply = "Please copy and paste the link to the message you want to report.\n"
                    reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
                    self.state = State.AWAITING_MESSAGE
                    return [reply]
                case self.USER_KEYWORD:
                    self.REPORT_INFO_DICT["Reporting"] = self.USER_KEYWORD
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
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]
            try:
                offending_message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems that this message was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]

            # Here we've found the message.
            self.state = State.MESSAGE_IDENTIFIED
            self.REPORT_INFO_DICT["Offending message link"] = message.content
            self.REPORT_INFO_DICT["Offending message author"] = offending_message.author.name
            self.REPORT_INFO_DICT["Offending message"] = offending_message.content
            reply = "I found this message:" + "```" + offending_message.author.name + ": " + offending_message.content + "```\n"
            reply += "What are you reporting this message for? Enter the number for the type of abuse from the list below. \n"
            for key, value in self.ABUSE_TYPES_DICT.items():
                reply += "\n" + key + ". " + value
            self.state = State.AWAITING_ABUSE_TYPE
            return [reply]
        
        # User is reporting a user profile.
        if self.state == State.AWAITING_USER:
            try:
                user = await self.client.fetch_user(message.content)
            except discord.errors.NotFound:
                return ["It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]
            
            # Here we've found the user.
            self.state = State.USER_IDENTIFIED
            self.REPORT_INFO_DICT["Offending user ID"] = user.id
            reply = "What are you reporting `" + user.name + "` for? Enter the number for the type of abuse from the list below.\n"
            for key, value in self.ABUSE_TYPES_DICT.items():
                reply += "\n" + key + ". " + value
            self.state = State.AWAITING_ABUSE_TYPE
            return [reply]            
        
        # User specifies the abuse type.
        if self.state == State.AWAITING_ABUSE_TYPE:
            # Other abuse type. Shallow implementation.
            if message.content.lower() in self.ABUSE_TYPES_DICT.keys() and self.ABUSE_TYPES_DICT[message.content] != "impersonation":
                self.REPORT_INFO_DICT["Abuse type"] = self.ABUSE_TYPES_DICT[message.content]
                reply = "Thank you for your report with the listed reason of `" + self.ABUSE_TYPES_DICT[message.content] + "`.\n\n"
                reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                reply += "Would you also like to block this user? Enter `yes` or `no`."
                self.state = State.AWAITING_BLOCK_DECISION
            # Impersonation
            elif message.content.lower() in self.ABUSE_TYPES_DICT.keys() and self.ABUSE_TYPES_DICT[message.content] == "impersonation":
                self.REPORT_INFO_DICT["Abuse type"] = self.ABUSE_TYPES_DICT[message.content]
                reply = "Who is this profile impersonating? Enter the number for the corresponding identity from the list below.\n"
                for key, value in self.IMPERSONATION_VICTIM_DICT.items():
                    reply += "\n" + key + ". " + value
                self.state = State.AWAITING_IMPERSONATION_VICTIM
            else:
                reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User specifies who is being impersonated.
        if self.state == State.AWAITING_IMPERSONATION_VICTIM:
            # The reporter is being impersonated.
            if message.content.lower() in self.IMPERSONATION_VICTIM_DICT.keys() and self.IMPERSONATION_VICTIM_DICT[message.content] == "me":
                self.REPORT_INFO_DICT["Impersonation victim"] = self.IMPERSONATION_VICTIM_DICT[message.content]
                reply = "Thank you for your report.\n\n"
                reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                reply += "Would you also like to block this user? Enter `yes` or `no`."
                self.state = State.AWAITING_BLOCK_DECISION
            # Someone who is not the reporter is being impersonated.
            elif message.content.lower() in self.IMPERSONATION_VICTIM_DICT.keys():
                self.REPORT_INFO_DICT["Impersonation victim"] = self.IMPERSONATION_VICTIM_DICT[message.content]
                reply = "Does the person being impersonated have a profile on this platform? You can say `yes`, `no`, or `I don't know`."
                self.state = State.AWAITING_HAS_INSTAGRAM_PROFILE
            else:
                reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User tells us if the impersonation victim has a profile on this platform.
        if self.state == State.AWAITING_HAS_INSTAGRAM_PROFILE:
            match message.content.lower():
                case "yes":
                    self.REPORT_INFO_DICT["Victim has profile"] = message.content.lower()
                    reply = "What is the real user ID of the person being impersonated?\n"
                    reply += "You can obtain this ID by turning on Developer Mode, right-clicking the user's name or profile picture, and clicking `Copy User ID`.\n\n"
                    reply += "Enter the user ID of the person being impersonated or say `I don't know`."
                    self.state = State.AWAITING_REAL_INSTAGRAM_PROFILE
                case "no":
                    # # If in the "impersonating someone I know" branch:
                    # reply = "Thank you for your report.\n\n"
                    # reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    # reply += "Would you also like to block this user? Enter `yes` or `no`."
                    # self.state = State.AWAITING_BLOCK_DECISION
                    self.REPORT_INFO_DICT["Victim has profile"] = message.content.lower()
                    reply = "Is this profile impersonating a real person (as in, not an AI-generated or otherwise fictional persona)? You can say `yes`, `no`, or `I don't know`."
                    self.state = State.AWAITING_IMPERSONATING_REAL_PERSON
                    return [reply]
                case "i don't know":
                    # # If in the "impersonating someone I know" branch:
                    # reply = "Thank you for your report.\n\n"
                    # reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    # reply += "Would you also like to block this user? Enter `yes` or `no`."
                    # self.state = State.AWAITING_BLOCK_DECISION
                    self.REPORT_INFO_DICT["Victim has profile"] = "unsure"
                    reply = "Is this profile impersonating a real person (as in, not an AI-generated or otherwise fictional persona)? You can say `yes`, `no`, or `I don't know`."
                    self.state = State.AWAITING_IMPERSONATING_REAL_PERSON
                    return [reply]
                case "i dont know":
                    # # If in the "impersonating someone I know" branch:
                    # reply = "Thank you for your report.\n\n"
                    # reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    # reply += "Would you also like to block this user? Enter `yes` or `no`."
                    # self.state = State.AWAITING_BLOCK_DECISION
                    self.REPORT_INFO_DICT["Victim has profile"] = "unsure"
                    reply = "Is this profile impersonating a real person (as in, not an AI-generated or otherwise fictional persona)? You can say `yes`, `no`, or `I don't know`."
                    self.state = State.AWAITING_IMPERSONATING_REAL_PERSON
                    return [reply]
                case _:
                    reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User tells us the real user ID of the impersonation victim.
        if self.state == State.AWAITING_REAL_INSTAGRAM_PROFILE:
            # User doesn't have real ID of impersonation victim. End reporting flow.
            if message.content.lower() == "i don't know" or message.content.lower() == "i dont know":
                self.REPORT_INFO_DICT["Victim user ID"] = "unknown"
                reply = "Thank you for your report.\n\n"
                reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                reply += "Would you also like to block this user? Enter `yes` or `no`."
                self.state = State.AWAITING_BLOCK_DECISION
                return [reply]
            # User (presumably) attempts to enter a user ID.
            try:
                user = await self.client.fetch_user(message.content)
            except discord.errors.NotFound:
                reply = "It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel. Or, if you don't have the user ID of the person being impersonated, say `I don't know`."
                return [reply]
            # Here we've found the user.
            self.state = State.USER_IDENTIFIED
            self.REPORT_INFO_DICT["Victim user ID"] = message.content
            reply = "Thank you. We've identified `" + user.name + "` from the user ID you've provided. Is this the username of the person being impersonated?\n"
            reply += "Say `yes` or `no`."
            self.state = State.AWAITING_REAL_INSTAGRAM_PROFILE_CONFIRM
            return [reply]
        
        # User confirms that the impersonation victim's profile we've retrieved is the correct one.
        if self.state == State.AWAITING_REAL_INSTAGRAM_PROFILE_CONFIRM:
            match message.content.lower():
                case "yes":
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    reply += "Would you also like to block this user? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                case "no":
                    self.REPORT_INFO_DICT.pop(list(self.REPORT_INFO_DICT)[-1])
                    reply = "It seems that you've entered the wrong user ID. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel. Or, if you don't have the user ID of the person being impersonated, say `I don't know`."
                    self.state = State.AWAITING_REAL_INSTAGRAM_PROFILE
                case _:
                    reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User tells us if the impersonation victim is a real person (as opposed to AI-generated or otherwise fictional persona).
        if self.state == State.AWAITING_IMPERSONATING_REAL_PERSON:
            # All of these are handled the same way. Only difference is in how it's recorded for the report the moderation team receives.
            match message.content.lower():
                case "yes":
                    self.REPORT_INFO_DICT["Victim is a real person"] = message.content.lower()
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    reply += "Would you also like to block this user? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                case "no":
                    self.REPORT_INFO_DICT["Victim is a real person"] = message.content.lower()
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    reply += "Would you also like to block this user? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                case "i don't know":
                    self.REPORT_INFO_DICT["Victim is a real person"] = "unknown"
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    reply += "Would you also like to block this user? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                case "i dont know":
                    self.REPORT_INFO_DICT["Victim is a real person"] = "unknown"
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    reply += "Would you also like to block this user? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                case _:
                    reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User decides whether to also block the user profile they are reporting.
        if self.state == State. AWAITING_BLOCK_DECISION:
            match message.content.lower():
                case "yes":
                    reply = "Ok. You will no longer see content or messages from this user."
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
    


    

