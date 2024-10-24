import os
import getpass
import socket

from IPython.terminal.prompts import Prompts, Token


class BashLikePrompt(Prompts):
    def in_prompt_tokens(self):
        return [
            (Token.Prompt, "In "),
            (Token, f"{getpass.getuser()}@{socket.gethostname()}:{os.getcwd()}"),
            (Token.Prompt, ' >>> '),
        ]


def setup_prompt(ipython):
    ipython.prompts = BashLikePrompt(ipython)

