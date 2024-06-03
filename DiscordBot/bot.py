# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
from report import State
from moderator import Moderate
import pdb
import numpy as np
import pandas as pd
from sklearn import preprocessing
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_val_score

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']


class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.moderations = {} # Map from report (message) ID to the state of the moderation
        self.reported_items = [] # List of reports
        self.watchlist = {}

        # Initialize classifier.
        self.classifier = LogisticRegression()
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.lb = preprocessing.LabelBinarizer()


    async def on_ready(self):
        print('Training classifier.')
        self.train_classifier()
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs).
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel.
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild :
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)


    async def handle_dm(self, message):
        # Handle a help message
        if message.content.lower() == Report.HELP_KEYWORD:
            reply =  "Use the `" + Report.START_KEYWORD + "` command to begin the reporting process.\n"
            reply += "Use the `" + Report.CANCEL_KEYWORD + "` command to cancel the reporting process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.lower().startswith(Report.START_KEYWORD) and not message.content.lower().startswith(Report.BLOCK_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to us
        if message.content.lower().startswith(Report.BLOCK_KEYWORD):
            self.reports[author_id].state = State.BLOCK_START
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete, add it to the list of reports and remove it from our map
        if self.reports[author_id].report_complete():
            self.reported_items.append(self.reports[author_id].REPORT_INFO_DICT.copy())
            self.reports[author_id].REPORT_INFO_DICT.clear()
            self.reports.pop(author_id)
        
        # If the report is cancelled, remove it from our map
        elif self.reports[author_id].report_cancelled():
            self.reports.pop(author_id)

        return


    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" and "group-#-mod" channels
        if not message.channel.name == f'group-{self.group_num}' and not message.channel.name == f'group-{self.group_num}-mod':
            return
        
        # Check each message in the "group-#" channel for impersonation and handle accordingly
        if message.channel.name == f'group-{self.group_num}':
            eval = self.eval_text(message)
            if eval > 0.5 or (eval > 0.4 and message.author.id in self.watchlist.keys()):
                self.reports[0] = Report(self)
                await self.reports[0].auto_report(message, eval)
                if self.reports[0].report_complete():
                    self.reported_items.append(self.reports[0].REPORT_INFO_DICT.copy())
                    self.reports[0].REPORT_INFO_DICT.clear()
                    self.reports.pop(0)

        # Handle mod messages while moderating reports.
        elif message.channel.name == f'group-{self.group_num}-mod':
            moderator_id = message.author.id
            responses = []

            # Only respond to messages if they're part of a moderation flow
            if moderator_id not in self.moderations and not message.content.lower().startswith(Moderate.START_KEYWORD):
                return

            # If we don't currently have an active moderation for this report, add one
            if moderator_id not in self.moderations:
                self.moderations[moderator_id] = Moderate(self)
                if len(self.reported_items) > 0:
                    self.moderations[moderator_id].report = self.reported_items[0]

            # Let the moderation class handle this message; forward all the messages it returns to us
            responses = await self.moderations[moderator_id].handle_message(message)
            for r in responses:
                await message.channel.send(r)

            # If the moderation is complete, remove it from our map
            if self.moderations[moderator_id].moderation_complete():
                # Update watch list if needed
                if self.moderations[moderator_id].watch != "":
                    if self.moderations[moderator_id].watch not in self.watchlist.keys():
                        self.watchlist[self.moderations[moderator_id].watch] = [self.moderations[moderator_id].report]
                    else:
                        self.watchlist[self.moderations[moderator_id].watch].append(self.moderations[moderator_id].report)
                # Remove the moderation instance and report from our map
                self.moderations.pop(moderator_id)
                self.reported_items = self.reported_items[1:]
            
            # If the moderation is cancelled, remove it from our map
            elif self.moderations[moderator_id].moderation_cancelled():
                self.moderations.pop(moderator_id)

        # Forward the message to the mod channel with evaluation scores in Milestone 3
        # mod_channel = self.mod_channels[message.guild.id]
        # await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')
        # scores = self.eval_text(message.content)
        # await mod_channel.send(self.code_format(scores))

        return

    
    def train_classifier(self):
        # Read data in and split into train and test groups.
        data = pd.read_csv('messages_dataset.csv')
        X_train, X_test, y_train, y_test = train_test_split(data['message'], data['label'], train_size = 0.8, random_state=7)

        # Labels need to be binarized to compute precision and recall.
        y_train = np.array([number[0] for number in self.lb.fit_transform(y_train)])
        y_test = np.array([number[0] for number in self.lb.fit_transform(y_test)])

        # Train the classifier after applying tf-idf vectorizer.
        X_tfidf_train = self.vectorizer.fit_transform(X_train)
        X_tfidf_test = self.vectorizer.transform(X_test)
        self.classifier.fit(X_tfidf_train, y_train)

        # Print accuracy, precision, and recall.
        accuracy = self.classifier.score(X_tfidf_test, y_test)
        precision = cross_val_score(self.classifier, X_tfidf_train, y_train, cv=10, scoring='precision')
        recall = cross_val_score(self.classifier, X_tfidf_train, y_train, cv=10, scoring='recall')
        print(f'Classifier accuracy is {accuracy * 100:.2f}%.')
        print(f"Classifier precision is {np.mean(precision):.2f}.")
        print(f"Classifier recall is {np.mean(recall):.2f}.")

        return

    
    def eval_text(self, message):
        return self.classifier.predict_proba(self.vectorizer.transform([message.content]))[0, 1]

    
    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel.
        '''
        return "Evaluated: '" + text + "'"


client = ModBot()
client.run(discord_token)
