# moderator.py
from enum import Enum, auto
import discord
import re

class State(Enum):
    MODERATION_START = auto()
    AWAITING_MESSAGE_CLEAR_VIOLATION = auto()
    AWAITING_USER_REPORT_PLAUSIBLE_VIOLATION = auto()
    AWAITING_MOD_IDENTIFY_POTENTIAL_VICTIM = auto()
    AWAITING_USER_REPORT_LIKELY_VIOLATION_UNK_VICTIM = auto()
    AWAITING_USERNAME_INPUT = auto()
    AWAITING_MALICIOUS_DECISION = auto()
    MODERATION_COMPLETE = auto()
    MODERATION_CANCELLED = auto()

class Moderate:
    START_KEYWORD = "!start"
    CANCEL_KEYWORD = "!cancel"

    def __init__(self, client):
        self.state = State.MODERATION_START
        self.client = client
        self.message = None
        self.report = {}
        self.watch = ""

    async def handle_message(self, message):
        '''
        This function makes up the meat of the moderation flow. It defines how we transition between states and what 
        prompts to offer at each of those states.
        '''

        # User cancels moderation.
        if message.content.lower() == self.CANCEL_KEYWORD:
            self.state = State.MODERATION_CANCELLED
            return ["Moderation cancelled."]
        
        # Moderator starts moderation process.
        if self.state == State.MODERATION_START:
            reply = "Thank you for starting the moderating process. "

            # Nothing on the list of reports.
            if len(self.report) == 0:
                reply += "There are currently no reports to review."
                self.state = State.MODERATION_COMPLETE
                return [reply]

            reply += "This is the next report in the moderation queue:\n"
            for key, value in self.report.items():
                reply += "\n" + key + ": " + str(value)

            # Other abuse type. Shallow implementation.
            if self.report["Abuse type"] != "impersonation":
                reply += "\n\nLet's pretend you went through a moderation flow for this abuse type and have taken all appropriate actions. No further action is necessary."
                self.state = State.MODERATION_COMPLETE
                return [reply]

            if self.report["Reporting"] == "message":
                reply += "\n\nIs the reported message authored by `" + self.report["Offending username"] + "` clear evidence of impersonation? Say `yes` or `no`."
                self.state = State.AWAITING_MESSAGE_CLEAR_VIOLATION

            elif self.report["Reporting"] == "user":
                # We have the victim's profile
                if self.report["Impersonation victim"] == "me" or "Victim user ID" in self.report.keys():
                    reply += "\n\nAfter reviewing the offender's and victim's profiles, is it plausible that the reported profile is impersonating the victim? Say `yes` or `no`."
                    self.state = State.AWAITING_USER_REPORT_PLAUSIBLE_VIOLATION
                # We don't have the victim's profile
                elif self.report["Impersonation victim"] == "someone I know":
                    reply += "\n\nCan you identify a potential victim the reported profile is impersonating? Say `yes` or `no`."
                    self.state = State.AWAITING_MOD_IDENTIFY_POTENTIAL_VICTIM
                # Reporter believes the victim is a real unknown person
                elif "Victim is a real person" in self.report.keys() and self.report["Victim is a real person"] == "yes":
                    reply += "\n\nCan you identify a potential victim the reported profile is impersonating? Say `yes` or `no`."
                    self.state = State.AWAITING_MOD_IDENTIFY_POTENTIAL_VICTIM
                # Victim may not be a real person
                elif "Victim is a real person" in self.report.keys() and self.report["Victim is a real person"] != "yes":
                    reply += "\n\nAfter a review of the reported user profile, is it likely that this is a case of impersonation? Say `yes` or `no`."
                    self.state = State.AWAITING_USER_REPORT_LIKELY_VIOLATION_UNK_VICTIM
                # Some combination not handled
                else:
                    reply += "\n\nSomething has gone wrong. Ending the moderation process."
                    self.state = State.MODERATION_CANCELLED

            return [reply]

        # Moderator decides whether message is a clear impersonation violation.
        if self.state == State.AWAITING_MESSAGE_CLEAR_VIOLATION:
            match message.content.lower():
                case "yes":
                    reply = "Does the impersonation seem to be for malicious purposes (as in, not satire or an open joke)? Say `yes` or `no`.\n"
                    self.state = State.AWAITING_MALICIOUS_DECISION
                case "no":
                    # We have the victim's profile
                    if self.report["Impersonation victim"] == "me" or "Victim user ID" in self.report.keys():
                        reply = "After reviewing the offender's and victim's profiles, is it plausible that the reported profile is impersonating the victim? Say `yes` or `no`."
                        self.state = State.AWAITING_USER_REPORT_PLAUSIBLE_VIOLATION
                    # We don't have the victim's profile
                    elif self.report["Impersonation victim"] == "someone I know":
                        reply = "Can you identify a potential victim the reported profile is impersonating? Say `yes` or `no`."
                        self.state = State.AWAITING_MOD_IDENTIFY_POTENTIAL_VICTIM
                    # Reporter believes the victim is a real unknown person
                    elif "Victim is a real person" in self.report.keys() and self.report["Victim is a real person"] == "yes":
                        reply = "Can you identify a potential victim the reported profile is impersonating? Say `yes` or `no`."
                        self.state = State.AWAITING_MOD_IDENTIFY_POTENTIAL_VICTIM
                    # Victim may not be a real person
                    elif "Victim is a real person" in self.report.keys() and self.report["Victim is a real person"] != "yes":
                        reply = "After a review of the reported user profile, is it likely that this is a case of impersonation? Say `yes` or `no`."
                        self.state = State.AWAITING_USER_REPORT_LIKELY_VIOLATION_UNK_VICTIM
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # Moderator reviews both offender's and victim's profiles and decides whether a violation is plausible.
        if self.state == State.AWAITING_USER_REPORT_PLAUSIBLE_VIOLATION:
            match message.content.lower():
                case "yes":
                    reply = "Does the impersonation seem to be for malicious purposes (as in, not satire or an open joke)? Say `yes` or `no`.\n"
                    self.state = State.AWAITING_MALICIOUS_DECISION
                case "no":
                    reply = "A warning has been issued to the reporter about false or malicious reports. They may appeal if they believe there has been a mistake. No further action is necessary."
                    self.state = State.MODERATION_COMPLETE
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # Moderator looks for a potential victim and indicates whether they have found one or not.
        if self.state == State.AWAITING_MOD_IDENTIFY_POTENTIAL_VICTIM:
            match message.content.lower():
                case "yes":
                    reply = "What is the potential victim's username?\n"
                    self.state = State.AWAITING_USERNAME_INPUT
                case "no":
                    reply = "After a review of the reported user profile, is it likely that this is a case of impersonation? Say `yes` or `no`."
                    self.state = State.AWAITING_USER_REPORT_LIKELY_VIOLATION_UNK_VICTIM
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # Moderator gives a potential victim they have found on the platform.
        if self.state == State.AWAITING_USERNAME_INPUT:
            try:
                memberID = await get_member_id(self.client, message.content)
                user = await self.client.fetch_user(memberID)
            except discord.errors.NotFound:
                return ["It seems that this user profile was deleted or never existed. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."]
            
            # Here we've found the user.
            self.report["Potential victim user ID"] = user.id
            reply = "After reviewing the offender's profile, is it likely that it is impersonating `" + user.name + "`? Say `yes` or `no`.\n"
            self.state = State.AWAITING_USER_REPORT_LIKELY_VIOLATION_UNK_VICTIM
            return [reply]
        
        # Moderator decides whether it is likely that the offender is impersonating the victim.
        if self.state == State.AWAITING_USER_REPORT_LIKELY_VIOLATION_UNK_VICTIM:
            match message.content.lower():
                case "yes":
                    reply = "Does the impersonation seem to be for malicious purposes (as in, not satire or an open joke)? Say `yes` or `no`.\n"
                    self.state = State.AWAITING_MALICIOUS_DECISION
                case "no":
                    self.watch = self.report["Offending user ID"]
                    reply = "There is insufficient information to take action on the reported user. Watch list has been updated with this report. No further action is necessary."
                    self.state = State.MODERATION_COMPLETE
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
        # Moderator determines whether impersonation seems malicious.
        if self.state == State.AWAITING_MALICIOUS_DECISION:
            match message.content.lower():
                case "yes":
                    reply = "A warning and permanent ban have been issued to the offender with the reason of `impersonation`. They may appeal if they believe there has been a mistake. No further action is necessary."
                    self.state = State.MODERATION_COMPLETE
                case "no":
                    reply = "A warning and 7-day ban have been issued to the offender with the reason of `impersonation`. They may appeal if they believe there has been a mistake. No further action is necessary."
                    self.state = State.MODERATION_COMPLETE
                case _:
                    reply = "That is not a valid response. Please try again or say `" + self.CANCEL_KEYWORD + "` to cancel."
            return [reply]
        
    def moderation_complete(self):
        return self.state == State.MODERATION_COMPLETE

    def moderation_cancelled(self):
        return self.state == State.MODERATION_CANCELLED

async def get_member_id(self, provided):
    """
    This function gets the unique member ID from a provided Discord Username for reporting purposes.
    :param self: The moderator reporting flow
    :param provided: The provided username of the supposed offender
    :return: member ID associated with the username
    """
    for guild in self.guilds:
        async for member in guild.fetch_members():
            if provided == member.name:
                return member.id