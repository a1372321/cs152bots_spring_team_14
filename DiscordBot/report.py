from enum import Enum, auto
import discord
import re

class State(Enum):
    BLOCK_START = auto()
    AWAITING_USER_TO_BLOCK = auto()
    AWAITING_REPORT_DECISION = auto()
    REPORT_START = auto()
    AWAITING_REPORT_TYPE = auto()
    AWAITING_MESSAGE = auto()
    AWAITING_USER = auto()
    MESSAGE_IDENTIFIED = auto()
    AWAITING_ABUSE_TYPE = auto()
    AWAITING_IMPERSONATION_VICTIM = auto()
    AWAITING_HAS_PROFILE = auto()
    AWAITING_IMPERSONATING_REAL_PERSON = auto()
    AWAITING_REAL_PROFILE = auto()
    AWAITING_BLOCK_DECISION = auto()
    REPORT_COMPLETE = auto()
    REPORT_CANCELLED = auto()

class Report:
    START_KEYWORD = "!report"
    CANCEL_KEYWORD = "!cancel"
    HELP_KEYWORD = "!help"
    BLOCK_KEYWORD = "!block"
    MESSAGE_KEYWORD = "message"
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
        if message.content.lower() == self.CANCEL_KEYWORD:
            self.state = State.REPORT_CANCELLED
            return ["Report cancelled."]
        
        # User starts by blocking process.
        if self.state == State.BLOCK_START:
            reply = "Please copy and paste the username of the user profile you wish to block.\n\n"
            reply += "You can obtain this by clicking the user's Display Name or profile picture and copying the username that appears below their Display Name in the resulting popup."
            self.state = State.AWAITING_USER_TO_BLOCK
            return [reply]
        
        # User blocks a user profile.
        if self.state == State.AWAITING_USER_TO_BLOCK:
            try:
                memberID = await get_member_id(self.client, message.content)
                if memberID == None:
                    reply = "It seems that this user profile is not in a guild I'm in. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                    return [reply]
                user = await self.client.fetch_user(memberID)
            except discord.errors.NotFound:
                return ["It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]

            # Here we've found the user.
            if user.id == message.author.id:
                reply = "You cannot block yourself. Please enter a different username or say `" + self.CANCEL_KEYWORD + "` to cancel."
            else:
                self.REPORT_INFO_DICT["Reporting"] = self.USER_KEYWORD
                self.REPORT_INFO_DICT["Offending user ID"] = user.id
                self.REPORT_INFO_DICT["Offending username"] = user.name
                reply = "Ok. You will no longer see content or messages from `" + self.REPORT_INFO_DICT["Offending username"] + "`.\n"
                reply += "Would you also like to report `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                self.state = State.AWAITING_REPORT_DECISION
            return [reply]
        
        # User decides whether to also report the user profile they are blocking.
        if self.state == State.AWAITING_REPORT_DECISION:
            match message.content.lower():
                case "yes":
                    self.REPORT_INFO_DICT["Offending user blocked"] = "yes"
                    reply = "Thank you for starting the reporting process. What are you reporting `" + self.REPORT_INFO_DICT["Offending username"] + "` for? Enter the number for the type of abuse from the list below.\n"
                    for key, value in self.ABUSE_TYPES_DICT.items():
                        reply += "\n" + key + ". " + value
                    self.state = State.AWAITING_ABUSE_TYPE
                case "no":
                    reply = "Ok."
                    self.state = State.REPORT_CANCELLED
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User starts reporting process.
        if self.state == State.REPORT_START:
            self.REPORT_INFO_DICT["Reporter"] = message.author.name
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `" + self.HELP_KEYWORD + "` at any time for more information on commands you can use.\n\n"
            reply += "Are you reporting a message or a user profile?\n"
            reply += "You can say `" + self.MESSAGE_KEYWORD + "` or `" + self.USER_KEYWORD + "`."
            self.state = State.AWAITING_REPORT_TYPE
            return [reply]
        
        # User specifies what they're reporting (message, user).
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
                    reply = "Please copy and paste the username of the user profile you wish to report.\n"
                    reply += "You can obtain this by clicking the user's Display Name or profile picture and copying the username that appears below their Display Name in the resulting popup."
                    self.state = State.AWAITING_USER
                    return [reply]
                case _:
                    reply = "That is not a valid response. Please say `" + self.MESSAGE_KEYWORD + "` or `" + self.USER_KEYWORD + "`, or say `" + self.CANCEL_KEYWORD + "` to cancel."
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
            self.REPORT_INFO_DICT["Offending user ID"] = offending_message.author.id
            self.REPORT_INFO_DICT["Offending username"] = offending_message.author.name
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
                memberID = await get_member_id(self.client, message.content)
                if memberID == None:
                    reply = "It seems that this user profile is not in a guild I'm in. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                    return [reply]
                user = await self.client.fetch_user(memberID)
            except discord.errors.NotFound:
                return ["It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]
            
            # Here we've found the user.
            self.REPORT_INFO_DICT["Offending user ID"] = user.id
            self.REPORT_INFO_DICT["Offending username"] = user.name
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
                if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                    reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                else:
                    self.state = State.REPORT_COMPLETE
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
                # The user is saying that they are the impersonator and the victim, which doesn't make sense.
                if self.REPORT_INFO_DICT["Offending username"] == message.author.name:
                    reply = "You cannot be impersonating yourself. Please enter `2` for `someone I know` or `3` for `someone else`, or say `" + self.CANCEL_KEYWORD + "` to cancel."
                # No strange logic. Continue.
                else:
                    self.REPORT_INFO_DICT["Impersonation victim"] = self.IMPERSONATION_VICTIM_DICT[message.content]
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                        reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                        self.state = State.AWAITING_BLOCK_DECISION
                    else:
                        self.state = State.REPORT_COMPLETE
            # Someone who is not the reporter is being impersonated.
            elif message.content.lower() in self.IMPERSONATION_VICTIM_DICT.keys():
                self.REPORT_INFO_DICT["Impersonation victim"] = self.IMPERSONATION_VICTIM_DICT[message.content]
                reply = "Does the person being impersonated have a profile on this platform? You can say `yes`, `no`, or `I don't know`."
                self.state = State.AWAITING_HAS_PROFILE
            else:
                reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User tells us if the impersonation victim has a profile on this platform.
        if self.state == State.AWAITING_HAS_PROFILE:
            match message.content.lower():
                case "yes":
                    self.REPORT_INFO_DICT["Victim has profile"] = message.content.lower()
                    reply = "What is the real username of the person being impersonated?\n"
                    reply += "You can obtain this by clicking the user's Display Name or profile picture and copying the username that appears below their Display Name in the resulting popup.\n\n"
                    reply += "Enter the username of the person being impersonated or say `I don't know`."
                    self.state = State.AWAITING_REAL_PROFILE
                case "no":
                    self.REPORT_INFO_DICT["Victim has profile"] = message.content.lower()
                    # "Impersonating someone I know" branch
                    if self.REPORT_INFO_DICT["Impersonation victim"] == self.IMPERSONATION_VICTIM_DICT["2"]:
                        reply = "Thank you for your report.\n\n"
                        reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                        if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                            reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                            self.state = State.AWAITING_BLOCK_DECISION
                        else:
                            self.state = State.REPORT_COMPLETE
                    # "Impersonating someone else" branch
                    else:
                        reply = "Is this profile impersonating a real person (as in, not an AI-generated or otherwise fictitious persona)? You can say `yes`, `no`, or `I don't know`."
                        self.state = State.AWAITING_IMPERSONATING_REAL_PERSON
                    return [reply]
                case "i don't know":
                    self.REPORT_INFO_DICT["Victim has profile"] = message.content.lower()
                    # "Impersonating someone I know" branch
                    if self.REPORT_INFO_DICT["Impersonation victim"] == self.IMPERSONATION_VICTIM_DICT["2"]:
                        reply = "Thank you for your report.\n\n"
                        reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                        if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                            reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                            self.state = State.AWAITING_BLOCK_DECISION
                        else:
                            self.state = State.REPORT_COMPLETE
                    # "Impersonating someone else" branch
                    else:
                        reply = "Is this profile impersonating a real person (as in, not an AI-generated or otherwise fictitious persona)? You can say `yes`, `no`, or `I don't know`."
                        self.state = State.AWAITING_IMPERSONATING_REAL_PERSON
                    return [reply]
                case "i dont know":
                    self.REPORT_INFO_DICT["Victim has profile"] = message.content.lower()
                    # "Impersonating someone I know" branch
                    if self.REPORT_INFO_DICT["Impersonation victim"] == self.IMPERSONATION_VICTIM_DICT["2"]:
                        reply = "Thank you for your report.\n\n"
                        reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                        if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                            reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                            self.state = State.AWAITING_BLOCK_DECISION
                        else:
                            self.state = State.REPORT_COMPLETE
                    # "Impersonating someone else" branch
                    else:
                        reply = "Is this profile impersonating a real person (as in, not an AI-generated or otherwise fictitious persona)? You can say `yes`, `no`, or `I don't know`."
                        self.state = State.AWAITING_IMPERSONATING_REAL_PERSON
                    return [reply]
                case _:
                    reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User tells us the real username of the impersonation victim.
        if self.state == State.AWAITING_REAL_PROFILE:
            # User doesn't have real username of impersonation victim. End reporting flow.
            if message.content.lower() == "i don't know" or message.content.lower() == "i dont know":
                self.REPORT_INFO_DICT["Victim user ID"] = "unknown"
                reply = "Thank you for your report.\n\n"
                reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                    reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                else:
                    self.state = State.REPORT_COMPLETE
                return [reply]
            # User (presumably) attempts to enter a username.
            try:
                memberID = await get_member_id(self.client, message.content)
                if memberID == None:
                    reply = "It seems that this user profile is not in a guild I'm in. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
                    return [reply]
                user = await self.client.fetch_user(memberID)
            except discord.errors.NotFound:
                reply = "It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel. Or, if you don't have the username of the person being impersonated, say `I don't know`."
                return [reply]
            # Here we've found the user.
            # The reporter is saying that the offender is impersonating themselves, which doesn't make sense.
            if user.id == self.REPORT_INFO_DICT["Offending user ID"]:
                reply = "This is the same user as the user you are reporting. Please enter a different username or say `" + self.CANCEL_KEYWORD + "` to cancel."
            # Got a potential impersonation victim user profile. End flow.
            else:
                self.REPORT_INFO_DICT["Victim user ID"] = user.id
                reply = "Thank you for your report.\n\n"
                reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                    reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                    self.state = State.AWAITING_BLOCK_DECISION
                else:
                    self.state = State.REPORT_COMPLETE
            return [reply]
        
        # User tells us if the impersonation victim is a real person (as opposed to AI-generated or otherwise fictitious persona).
        if self.state == State.AWAITING_IMPERSONATING_REAL_PERSON:
            # All of these are handled the same way. Only difference is in how it's recorded for the report the moderation team receives.
            match message.content.lower():
                case "yes":
                    self.REPORT_INFO_DICT["Victim is a real person"] = message.content.lower()
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                        reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                        self.state = State.AWAITING_BLOCK_DECISION
                    else:
                        self.state = State.REPORT_COMPLETE
                case "no":
                    self.REPORT_INFO_DICT["Victim is a real person"] = message.content.lower()
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                        reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                        self.state = State.AWAITING_BLOCK_DECISION
                    else:
                        self.state = State.REPORT_COMPLETE
                case "i don't know":
                    self.REPORT_INFO_DICT["Victim is a real person"] = "unknown"
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                        reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                        self.state = State.AWAITING_BLOCK_DECISION
                    else:
                        self.state = State.REPORT_COMPLETE
                case "i dont know":
                    self.REPORT_INFO_DICT["Victim is a real person"] = "unknown"
                    reply = "Thank you for your report.\n\n"
                    reply += "Our content moderation team will review the report and take appropriate actions according to our Community Guidelines. Note that your report is anonymous. The account you reported will not see who reported them.\n\n"
                    if "Offending user blocked" not in self.REPORT_INFO_DICT.keys() and self.REPORT_INFO_DICT["Offending user ID"] != message.author.id:
                        reply += "Would you also like to block `" + self.REPORT_INFO_DICT["Offending username"] + "`? Enter `yes` or `no`."
                        self.state = State.AWAITING_BLOCK_DECISION
                    else:
                        self.state = State.REPORT_COMPLETE
                case _:
                    reply = "That was not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # User decides whether to also block the user profile they are reporting.
        if self.state == State.AWAITING_BLOCK_DECISION:
            match message.content.lower():
                case "yes":
                    reply = "Ok. You will no longer see content or messages from `" + self.REPORT_INFO_DICT["Offending username"] + "`."
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
    
    def report_cancelled(self):
        return self.state == State.REPORT_CANCELLED


async def get_member_id(self, provided):
    """
    This function gets the unique member ID from a provided Discord Username for reporting purposes.
    :param self: The user reporting flow
    :param provided: The user provided username (to be reported)
    :return: member ID associated with the username
    """
    for guild in self.guilds:
        async for member in guild.fetch_members():
            if provided == member.name:
                return member.id
    return None
