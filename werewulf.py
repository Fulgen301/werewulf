#!/usr/bin/env python3

from enum import IntEnum
from bs4 import BeautifulSoup
import random
import sys
import threading
import pickle
import warnings
import time
import re
import enet
import asyncio

PORT = 9621

if sys.version_info < (3,6):
    raise RuntimeError("Python version {} lower than 3.6".format(sys.version_info))
class Time(IntEnum):
    Day = 1
    Night = 2
    Both = 3

class MessageType(IntEnum):
    Unknown = -1
    Update = 1
    GameState = 2
    Reset = 3
    PlayerInput = 4

class GameState(IntEnum):
    Lobby = 0
    Running = 1

class PlayerInput(IntEnum):
    String = 0
    Player = 1

class Person(object): pass
class BasicRole(object): pass
class Game(object): pass
class Roles(object):
    class Werewulf(object): pass

class Person(object):
    role = None
    alive = True
    killable = True
    AI = True
    name = None
    game = None
    client = None
    
    def __init__(self, role : BasicRole, game : Game, AI : bool = True, name : str = None, client = None) -> None:
        assert type(name) == str, "{}".format(name)
        self.role = role
        assert type(self.role) is not type, f"{self.role}"
        self.AI = AI
        self.name = name if name else "Person"
        self.client = client
    
    @classmethod
    def withNameFromList(cls, role : BasicRole, game : Game, AI : bool = True, name_list : list = None, client = None) -> Person:
        name = None
        assert name_list
        if name_list:
            random.shuffle(name_list)
            name = name_list.pop()

        return cls(role, game, AI, name, client)
    
    def kill(self) -> None:
        self.alive = False
        self.killable = False
    
    def __repr__(self) -> str:
        return self.name

    def __call__(*args):
        return self.role(self.game, self, *args)

    def getVoteTarget(self):
        return self.role.getVoteTarget(self.game, self)
    
    def isHostile(self):
        return self.role.isHostile()

class BasicRole(object):
    time = Time.Day
    index = 0
    
    def __repr__(self) -> str:
        return self.__class__.__name__.lower()
    
    def __call__(self, game : Game, person : Person) -> bool:
        return True
    
    def hasWon(self, game : Game, time : int = None) -> bool:
        return len(list(game.getPlayersByFilter(lambda person: person.alive and person.role.__class__ == Roles.Werewulf))) == 0

    def isValidVoteTarget(self, person : Person) -> bool:
        return True
    
    def isHostile(self) -> bool:
        return False

    def getVoteTarget(self, game : Game, person : Person) -> Person:
        if person.AI:
            return random.choice(game.getPlayersByFilter(lambda p: p.alive and p.killable and self.isValidVoteTarget(p)))
        else:
            while True:
                victim = game.getPlayer(input("Enter a victim's name: \n> "), lambda x: x.alive and x.killable and x != person)
                if victim:
                    return victim
                    break
                else:
                    print("Invalid vote. Maybe you tried voting for your own death.")

class Roles(object):
    class Werewulf(BasicRole):
        time = Time.Night
        index = 5
        
        def __call__(self, game : Game, person : Person) -> bool:
            if game.getVictims() != []: return True #WARNING: All roles which designate a victim must awake after the werewulves!
            available = list(game.getPlayersByFilter(lambda x: x.alive and x.killable and x.role != self))
            
            if person.AI == False and person.alive:
                while True:
                    victim = game.getPlayer(input("Enter a victim's name: \n> "), lambda x: x.alive and x.killable and type(x.role) != type(self))
                    if victim:
                        break
                    else:
                        print(f"Invalid victim. Maybe you tried killing yourself or another werewulf, or a protected person.")
            else:
                victim = random.choice(list(game.getPlayersByFilter(lambda x: x.alive and x.killable and not isinstance(x.role, type(self)))))
            game.addVictim(victim)
            return True

        def hasWon(self, game : Game, time : int = None) -> bool:
            return len(list(game.getPlayersByFilter(lambda person: person.alive and person.role.__class__ != self.__class__))) <= 1

        def isValidVoteTarget(self, person : Person) -> bool:
            return not isinstance(person.role, type(self))
        
        def isHostile(self) -> bool:
            return True
    
    class Villager(BasicRole):
        time = Time.Day
    
    class Witch(BasicRole):
        time = Time.Night
        index = 6
        potions = ["heal", "kill", "nothing"]

        def __call__(self, game : Game, person : Person) -> bool:
            if len(game.getVictims()) == 0 or len(self.potions) == 1:
                return True

            if person.AI == False:
                victim = game.getVictim()

                print(f"Victim: {victim} ({victim.role})")
                print("What do you want to do? (Available: {})\nUse multiple potions by entering them separated with a space.".format(
                    ", ".join(str(i) for i in self.potions)
                    ))
                ptn = input("> ").split(" ")
                for p in ptn:
                    if p not in self.potions:
                        print(f"ERROR: \"{p}\" is not a valid potion. Ignoring.")
                        continue
                    else:
                        if p == "heal":
                            print(f"{victim} will stay alive.")
                            game.removeVictim(victim)
                            
                        elif p == "kill":
                            while True:
                                second_victim = game.getPlayer(input(
                                        "Enter a victim's name. Available: {} \n> ".format(", ".join(str(i) for i in game.getPlayersByFilter(lambda p: p.alive and p.killable and p.role != self)))
                                    ), lambda x: x != self and x.alive and x.killable)
                                if second_victim:
                                    game.addVictim(second_victim)
                                    print(f"{second_victim} will be killed.")
                                    break
                                else:
                                    print(f"Invalid victim. Maybe you tried killing yourself or a protected person.")

                    if p != "nothing":
                        self.potions.remove(p)
            else:
                victim = game.getVictim()
                ptn = random.choice(self.potions) if victim != self else "heal" # Always heal yourself if you are the victim
                if ptn == "heal":
                    game.removeVictim(victim)
                elif ptn == "kill":
                    for i in range(100):
                        second_victim = random.choice(list(game.getPlayersByFilter(lambda p: p.alive and p.killable and p != self and p not in game.getVictims())))
                        if second_victim:
                            game.addVictim(second_victim)
                            break

                if ptn != "nothing":
                    self.potions.remove(ptn)
                    
    
    class Seer(BasicRole):
        time = Time.Night
        index = 7
        last = None

        def __call__(self, game : Game, person : Person) -> bool:
            if person.AI == False:
                while True:
                    victim = game.getPlayer(input("Enter the name of a person you want to see the role of: \n> "), lambda x: x.alive and x.killable and type(x.role) != type(self))
                    if victim:
                        print(f"The role of {victim} is {victim.role}.")
                        break
                    else:
                        print(f"Invalid person.")
            else:
                victim = random.choice(list(game.getPlayersByFilter(lambda p: p != self.last and p.alive and p.killable and p.isHostile())))
                if victim:
                    self.last = victim
            return True
        
        def getVoteTarget(self, game : Game, person : Person) -> Person:
            if not person.AI:
                return super().getVoteTarget(game, person)
            elif self.last and self.last.alive and self.last.killable:
                return self.last
            

class Game(object):
    loop = None
    people = []
    player_count = 8
    player_role = None
    _current_victims = []
    accused = {}
    role_sets = {
        "standard" : {
            Roles.Werewulf : [1, 4],
            Roles.Villager : None,
            Roles.Witch : 1,
            Roles.Seer : 1
        }
    }
    
    chosen_set = None
    network = None
    status = GameState.Lobby
    spectator = False
    nick = "Player"
    clients = []
    
    name_list = ["Alpha", "Beta", "Gamma", "Delta", "Max", "John", "Valentin", "Sarah", "Jane", "Ypsilon"]
    sync_attrs = ["people", "player_count", "_current_victims", "accused"]
    
    def __init__(self, loop) -> None:
        self.loop = loop
        print("Welcome to Werewulf.")
        self.selectNetworkMode()
        if not self.isNetwork():
            self.main()
        else:
            self.startLobby()
    
    def __getstate__(self) -> dict:
        state = dict()
        for i in self.sync_attr:
            state[i] = getattr(self, i)
        return state
    
    def __setstate__(self, state) -> None:
        self.__dict__.update(state)
    
    def selectNetworkMode(self) -> None:
        while True:
            c = input("Do you want to host or join a multiplayer game, or just play alone with an AI?\n(host, join, alone)\n>")
            print(c)
            if c == "host":
                self.showPlayerDialogue()
                self.hostGame()
                break

            elif c == "join":
                self.showPlayerDialogue()
                self.joinGame()
                break
            elif c == "alone":
                self.showPlayerDialogue()
                break
    
    def showPlayerDialogue(self) -> None:
        #while True:
        #	try:
        #		self.chosen_set = self.role_sets[input(f"Please specify the used set.\nAvailable: {self.role_sets}\n> ")]
        #		break
        #	except KeyError:
        #		print("ERROR: This set does not exist.")
        self.chosen_set = self.role_sets["standard"]

        self.nick = input("Enter your nick:\n> ")
        
        if self.isClient():
            return
        
        if self.isHost():
            while True:
                role = input("Do you want to be a spectator? (y/n)\n> ")
                
                if role == "y":
                    self.spectator = True
                break
        
        while True:
            try:
                self.player_count = int(input("Please specify the player count.\n> ")) - 1
                while len(self.name_list) < self.player_count:
                    self.name_list.append(f"Player {len(self.name_list)}")
                break
            except ValueError:
                print("ERROR: You did not enter a valid integer.")

    def hostGame(self) -> None:
        self.network = WWNetworkUDPServer(self)

    def joinGame(self) -> None:
        while True:
            try:
                addr = enet.Address(input("Enter the host name or the ip address of the host:\n> "), PORT)
            except OSError:
                print("ERROR: The entered host name is invalid.")
                continue
            

            self.network = WWNetworkUDPClient(self, addr)
            self.network.sendToHost(self.network.createMessage(MessageType.GameOpen))
            try:
                msg = self.network.requestMessage(MessageType.GameOpen, self.network.server, 20)
                if len(msg) < 2 or msg[1] != True:
                    raise ConnectionRefusedError
                break

            except (TimeoutError, ConnectionRefusedError):
                print("ERROR: It seems that the specified device does not run any valid games.")
        self.network.sendToHost(self.network.createMessage(MessageType.NewClient, self.network.getExternalIPAddress(), self.nick, self.spectator))

    async def startLobby(self) -> None:
        if not self.isNetwork():
            return
        
        if self.isHost():
            threading.Thread(target=self.checkMessages).start()

        while self.status == GameState.Lobby:
            ipt = input("Chat:|> ")
            if ipt.startswith("/start"):
                if self.isHost():
                    self.network.sendToClients(self.network.createMessage(MessageType.GameState, GameState.Running))
            else:
                self.log(f"<{self.nick}> {ipt}")
            time.sleep(0.1)
                
    
    def checkMessages(self) -> None:
        lastmsg = None
        while True:
            if not self.network.lastmsg or (self.network.lastmsg == lastmsg):
                time.sleep(1)
                continue
            msg = self.network.lastmsg.msg
            if msg:
                if lastmsg == msg:
                    continue
                
                lastmsg = msg
                if msg[0] == MessageType.NewClient:
                    if len(msg) >= 3:
                        self.log(f"Client {msg[2]} connected.")
                elif msg[0] == MessageType.RemoveClient:
                    if len(msg) >= 2:
                        self.log(f"Client {msg[2]} disconnected.")
                elif msg[0] == MessageType.GameState:
                    self.status = msg[1]
                    if self.status == GameState.Running:
                        self.main()

    def setupPlayers(self) -> None:
        last = []
        for role in self.chosen_set:
            choice = random.choice(clients)
            if type(self.chosen_set[role]) == list:
                while self.getRoleCount(role) < (self.player_count // self.chosen_set[role][1] * self.chosen_set[role][0]):
                    choice = random.choice(clients)
                    self.people.append(Person(role(), self, False, self.network.nicks.get(choice) or "Player"))
                    clients.remove(choice)

            elif self.chosen_set[role] == None:
                last.append(role)

            elif type(self.chosen_set[role]) == int:
                while self.getRoleCount(role) < self.chosen_set[role]:
                    choice = random.choice(clients)
                    self.people.append(Person(role(), self, False, self.network.nicks.get(choice) or "Player"))
                    clients.remove(choice)

        for i in clients:
            role = last.pop()
            self.people.append(Person(role(), self, False, self.networks.nick.get(i) or "Player"))
    
    def createSinglePlayer(self):
        self.people.append(Person(random.choice(list(self.chosen_set.keys()))(), self, False, self.nick or "Player"))
    
    def setupAI(self) -> None:
        last = []
        for role in self.chosen_set:
            if type(self.chosen_set[role]) == list:
                while self.getRoleCount(role) < (self.player_count // self.chosen_set[role][1] * self.chosen_set[role][0]):
                    self.addAI(role(), None)
            
            elif self.chosen_set[role] == None:
                last.append(role)
            
            elif type(self.chosen_set[role]) == int:
                while self.getRoleCount(role) < self.chosen_set[role]:
                    self.addAI(role(), None)
        
        needed = max(self.player_count - len(self.people), 0)
        if not needed: return
        
        for role in last:
            for i in range(needed // len(last)):
                self.addAI(role(), None, True)
    
    async def main(self) -> None:
        await self.startLobby()
        print("END: Lobby")
        if not self.isClient():
            old_maxplayer = self.player_count
            # Hacks
            if self.isHost():
                self.player_count -= self.network.getClientCount() if self.isNetwork() else 0
                self.setupPlayers()
            
            elif not self.isNetwork():
                self.createSinglePlayer()
            self.setupAI()

            self.player_count = old_maxplayer
            
            for i in self.people:
                assert i.role, f"{i, i.role}"
            
            self.people.sort(key=lambda x: (x.role.index, x.AI))
            
            if self.isHost():
                self.sendReset()
            
            if not self.spectator:
                print(f"You are a {self.getHumanPlayer()}") # FIXME
            while self.night() and self.day(): pass
    
    def day(self) -> bool:
        if self.isClient():
            while not self.checkFulfilled():
                msg = self.network.requestMessage(MessageType.Update)
                if len(msg) >= 2 and msg[1] == Time.Night:
                    return True

        self.accused = {}
        self.log("Night is over. The village awakes.\n")
        if self.getVictims() != []:
            for i in self.getVictims():
                self.log(f"{i}, a {i.role}, has been killed.")
                i.kill()
                self.removeVictim(i)

        else:
            self.log("No one has been killed.")

        self.log("Alive: %s\n" % ", ".join(i.name for i in self.getPlayersByFilter(lambda x: x.alive)))
        
        if self.checkFulfilled():
            return False

        for player in self.getPlayersByFilter(lambda person: person.AI == False and person.alive):
            while True:
                victim = self.requestPlayerInput(player.client,
                                        PlayerInput.Player,
                                        "Enter a victim's name:\n> ",
                                        "Invalid vote. Maybe you tried voting for your own death.",
                                        "lambda p: p.alive and p.killable")
                if victim and victim != player:
                    break

                self.log("Invalid vote. Maybe you tried voting for your own death.", player.client)

            self.addAccusedPlayer(victim, 0)
        
        for i in range(2):
            self.addAccusedPlayer(random.choice(list(self.getPlayersByFilter(lambda p: p.alive and p not in self.accused))), 0)
        
        while len(self.accused) > 1:
            
            self.log("Accused: %s" % ", ".join(str(i) for i in self.accused))
            
            for person in self.getPlayersByFilter(lambda person: person.alive):
                shall_continue = False
                
                if person.AI:
                    victim = random.choice(list(self.accused))
                    while victim == person or not person.role.isValidVoteTarget(victim):
                        if len(self.accused) == 1:	# only one victim
                            shall_continue = True
                            break
                        
                        victim = random.choice(list(self.accused))
                    
                    if shall_continue: continue
                    self.addAccusedPlayer(victim, self.accused[victim] + 1)
                else:
                    while True:
                        victim = self.requestPlayerInput(
                            person.client,
                            PlayerInput.Player,
                            "Enter the name of the person you want to get killed. Available: {}\n> ".format(", ".join(str(i) for i in self.accused.keys())),
                            "Invalid vote.",
                            "lambda x: x.alive and x.killable")
                        if victim in self.accused:
                            break
                        self.log("Invalid vote.", person.client)
                    self.addAccusedPlayer(victim, self.accused[victim] + 1)
            
            items = list(self.accused.items())
            items.sort(key=lambda x: x[1], reverse=True)
            self.log("\nVotes:")
            for i in items:
                self.log(f"{i[0]}: {i[1]}")
            
            self.accused.pop(items[-1][0])
        
        victim = list(self.accused.items())[0][0]
        victim.kill()
        self.log(f"{victim}, a {victim.role}, has been killed.\n")

        if self.checkFulfilled():
            return False
        
        self.log("The village sleeps.")
        return True
    
    def night(self):
        if self.isClient():
            while True:
                msg = self.network.requestMessage(MessageType.Update)
                if len(msg) >= 2 and msg[1] == Time.Day:
                    return True
        self.log("Night starts. Alive: %s\n" % ", ".join(i.name for i in self.getPlayersByFilter(lambda x: x.alive)))
        
        for person in self.getPlayersByFilter(lambda person: person.alive and \
                                            person.role.time & Time.Night and \
                                            ((self.isHost() and not person.AI) or True)):
            self.log(f"The {person.role} awakes.")
            person.role(self, person)
            self.log(f"The {person.role} sleeps.\n")
        if self.isHost():
            self.network.sendToClients(self.network.createMessage(MessageType.Update, Time.Day))
        return True

    def checkFulfilled(self, time=None):
        res = list(self.getPlayersByFilter(lambda person: person.alive and person.role.hasWon(self, time) and ((time and person.time & time) or True)))
        if len(res):
            self.log("{} ha{} won.".format(", ".join(f"{i} ({i.role})" for i in res), "ve" if len(res) > 1 else "s"))
            return True

    def doSync(self, f, *args) -> None:
        if not self.isHost():
            return
        msg = self.network.createMessage(MessageType.Update, {f : args})
        self.network.sendToClients(msg)

    def sendReset(self) -> None:
        if not self.isHost():
            return

        d = {}

        for i in self.sync_attrs:
            if hasattr(self, i):
                d[i] = getattr(self, i)

        self.network.sendToClients(self.network.createMessage(MessageType.Reset, d))

    def applyReset(self, reset : dict) -> None:
        if self.isHost():
            return

        for i in reset:
            setattr(self, i, reset[i])
            attr = getattr(self, i)
            if hasattr(attr, "game"):
                attr.game = self
            if hasattr(attr, "role"):
                attr.role = type(attr.role)()

    # Methods
    def getRoleCount(self, role : BasicRole, time : int = None) -> int:
        """Returns the number of people with the role <role> and, if specified, the acting time <time>."""
        return len(list(self.getPlayersByFilter(lambda person: person.role.__class__ == role and ((time and person.role.time & time) or True))))
    
    def getHumanPlayer(self) -> Person:
        """Returns the local human player. """
        return self.getPlayerByFilter(lambda person: person.AI == False and person.game == self)
    
    def getPlayer(self, name : str, fltr) -> Person:
        return self.getPlayerByFilter(lambda person: person.name == name and fltr(person))
    
    def getPlayerByFilter(self, fltr : filter) -> Person:
        for i in self.getPlayersByFilter(fltr):
            return i
    
    def getPlayersByFilter(self, fltr : filter) -> filter:
        return filter(fltr, self.people)

    def getPlayerByName(self, name) -> Person:
        if not isinstance(name, Person):
            name = self.getPlayerByFilter(lambda p: p.name == name)
        return name

    
    def addAI(self, role : BasicRole, name : str = None, sync : bool = True) -> None:
        if name == None:
            ai = Person.withNameFromList(role, self, True, self.name_list)
        else:
            ai = Person(role, self, True, name)
        
        self.people.append(ai)
        if sync: self.doSync("addAI", role, name)

    
    def addVictim(self, victim : Person, sync : bool = True) -> None:
        if victim not in self._current_victims:
            self._current_victims.append(victim)
            if sync: self.doSync("addVictim", victim)

    
    def removeVictim(self, victim : Person, sync : bool = True) -> None:
        if victim in self._current_victims:
            self._current_victims.remove(victim)
            if sync: self.doSync("removeVictim", victim)

    
    def killPlayer(self, victim, sync : bool = True) -> None:
        victim = self.getPlayerByName(victim)
        if not (victim and isinstance(victim, Person)):
            return

        victim.kill()
        if sync: self.doSync("killPlayer", victim)

    
    def addAccusedPlayer(self, victim, votes : int = 0, sync : bool = True) -> None:
        victim = self.getPlayerByName(victim)
        if not isinstance(victim, Person):
            print("returned")
            return

        self.accused[victim] = votes
        if sync: self.doSync("addAccusedPlayer", victim, votes)

    
    def removeAccusedPlayer(self, victim, sync : bool = True) -> None:
        victim = self.getPlayerByName(victim)
        if not (victim and isinstance(victim, Person) and victim in self.accused):
            return

        del self.accused[victim]
        if sync: self.doSync("removeAccusedPlayer", victim)

    def getVictims(self) -> list:
        return self._current_victims[:] # return a copy to prevent hacking
    
    def getVictim(self) -> Person:
        return self.getVictims()[0]

    def isHost(self) -> bool:
        return self.network and self.network.isServer()

    def isClient(self) -> bool:
        return self.network and self.network.isClient()

    def isNetwork(self) -> bool:
        return bool(self.network)

    def requestPlayerInput(self,
                        client : str = None,
                        ipt_type : int = PlayerInput.String,
                        prompt : str = "> ",
                        error_msg = "Please try again.",
                        fltr = "lambda person: True") -> str:
        if self.isNetwork():
            return self.network.requestPlayerInput(client, ipt_type, prompt, error_msg, fltr)
        while True:
            ipt = input(prompt)
            if ipt_type == PlayerInput.Player:
                ipt = self.getPlayerByFilter(lambda p: p.name == ipt and eval(fltr, globals(), locals())(p))
                if ipt:
                    break
                else:
                    print(error_msg)
        return ipt

    
    def log(self, message, client=None, sync = True) -> None:
        if not (self.isNetwork() and self.network.getExternalIPAddress() == client):
            pass

        print(message)
        if sync: self.doSync("log", message)
    
    async def startServer(self):
        self.server = asyncio.start_server(self.handleIncomingPacket, "127.0.0.1", PORT, loop=self.loop)
    
    async def handleIncomingPacket(self, reader, writer):
        pass

#				#
#	Network		#
#				#

class InvalidMessageError(TypeError): pass
class _Message(object): pass

class WWNetworkUDP(object):
    lastmsg = None

    def _assertIsValidIP(self, ip : str) -> None:
        try:
            assert re.match("([0-9]{1,3}|\.)", ip), f"Invalid IP: {ip}"
        except AssertionError:
            assert re.match(r".*\.local", ip), f"Invalid IP: {ip}"

    def _assertIsValidMessage(self, msg : list) -> None:
        if type(msg) != list:
            raise TypeError(f"Invalid message: {msg}")
    
    def _bindSocket(self):
        pass

    # Methods

    def createMessage(self, type : int, *args) -> list:
        #if type not in MessageType.__members__.__values__():
        #    raise InvalidMessageError("Invalid message type")

        l = [type, *args]
        return l

    def sendToClients(self, msg : object) -> None:
        pass

    def sendToClient(self, client : str, msg : object) -> None:
        pass

    def sendToHost(self, msg : object) -> None:
        pass

    def requestMessage(self, msg_type : int, peer : enet.Peer = None, timeout : int = None) -> list:
        start_time = time.time()
        while not (self.lastmsg and self.lastmsg.msg[0] == msg_type and ((peer and self.lastmsg.peer == peer) or True)):
            if timeout and (time.time() - start_time) >= timeout:
                raise TimeoutError
        return self.lastmsg.msg[:]

    def getExternalIPAddress(self) -> str:
        from urllib.request import urlopen
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(urlopen("http://whatismyip.org").read().decode("utf-8", "ignore"), "lxml")
        return soup.body.div.next_sibling.next_sibling.span.text

    def isClient(self) -> bool:
        return False
    
    def isServer(self) -> bool:
        return False

class WWNetworkUDPClient(enet.Host, WWNetworkUDP):
    game = None
    peer = None
    def __init__(self, game, addr) -> None:
        self.game = game
        super().__init__(None, 1, 2, 0, 0)
        self.connect(addr, 2, 0)
        
        if self.service(5000).type != enet.EVENT_TYPE_CONNECT:
            raise ConnectionRefusedError(f"Couldn't connect to {addr.host}:{addr.port}")
        
        threading.Thread(target=self.receive).start()
    
    def receive(self):
        while True:
            event = self.service(0)
            if event.type == enet.EVENT_TYPE_RECEIVE:
                self.handle(event.packet.data, event.address)

    def handle(self, data : bytes, address : enet.Address) -> None:
        try:
            msg = pickle.loads(data)
        except Exception: # not for us
            raise
        print(msg)
        self._assertIsValidMessage(msg)
        self.lastmsg = _Message()
        setattr(self.lastmsg, "msg", msg)
        setattr(self.lastmsg, "client", address)

        if msg[0] == MessageType.GameOpen:
            if len(msg) < 2:
                self.sendToHost(self.createMessage(MessageType.GameOpen, False))

        elif msg[0] == MessageType.Update:
            if len(msg) >= 2 and isinstance(msg[1], dict):
                print("Iterating through msg[1]...")
                for key in msg[1]:
                    print(f"hasattr: {hasattr(self, key)}")
                    if hasattr(self, key):
                        print(f"{key}({msg[1][key]})")
                        getattr(self, key)(*msg[1][key], sync=False)
            else:
                raise InvalidMessageError(f"{msg}, {len(msg) >= 2}, {isinstance(msg[1], dict)}")

        elif msg[0] == MessageType.Reset:
            if len(msg) >= 2 and isinstance(msg[1], dict):
                self.game.applyReset(msg[1])

        elif msg[0] == MessageType.PlayerInput:
            while True:
                ipt = input(msg[2])
                if msg[1] == PlayerInput.Player:
                    ipt = self.game.getPlayerByFilter(lambda p: p.name == ipt and (eval(msg[4]) if len(msg >= 5) else lambda p: True)(p))
                    if ipt:
                        break
                    else:
                        print(msg[3] if len(msg) >= 4 else "Please try again.")

            self.sendToHost(self, self.createMessage(MessageType.PlayerInput, ipt))

        elif msg[0] == MessageType.GameState:
            self.game.status = msg[1]

    def sendToHost(self, msg : object) -> None:
        msg = pickle.dumps(msg) # no exception handling, because this must NOT fail
        packet = enet.Packet(msg, enet.PACKET_FLAG_RELIABLE)
        self.peers[0].send(0, packet)
    
    def isClient(self) -> bool:
        return True

class WWNetworkUDPServer(enet.Host, WWNetworkUDP):
    def __init__(self, game) -> None:
        super().__init__(enet.Address("localhost", PORT), 32, 2, 0, 0)
        self.game = game
        threading.Thread(target=self.receive).start()
    
    def receive(self) -> None:
        while True:
            event = self.service(0)
            if event.type != 0:
                print(f"Event:", event.type)
            
            if event.type == enet.EVENT_TYPE_RECEIVE:
                self.handle(event.packet.data, event.peer)
        
    def handle(self, data : bytes, peer : enet.Peer) -> None:
        msg = pickle.loads(data)
        self._assertIsValidMessage(msg)

        self.lastmsg = _Message()
        setattr(self.lastmsg, "msg", msg)
        setattr(self.lastmsg, "client", peer)

        print(msg)

        if msg[0] == MessageType.GameOpen:
            self.sendToClient(peer, self.createMessage(MessageType.GameOpen, True))
        
        elif msg[0] == MessageType.Update:
            # Format of msg: [type, {str(function name) : tuple(args), ...}]
            clients = self.getClients()[:]
            clients.remove(peer)
            for c in clients:
                self.sendToClient(c, msg)
        
        
    def sendToClients(self, message : list) -> None:
        packet = enet.Packet(pickle.dumps(message), enet.PACKET_FLAG_RELIABLE)
        self.broadcast(0, packet)

    def sendToClient(self, peer : enet.Peer, message : list) -> None:
        packet = enet.Packet(pickle.dumps(message), enet.PACKET_FLAG_RELIABLE) # no exception handling, because this must NOT fail
        peer.send(0, packet)

    def getClients(self) -> list:
        return self.peers

    def getClientCount(self) -> int:
        return len(self.peers)

    def requestPlayerInput(self,
                        peer : enet.Peer,
                        ipt_type : int = PlayerInput.String,
                        prompt : str = "> ",
                        error_msg : str = "Please try again.",
                        fltr : str = "lambda person: True") -> str:
        
        msg = self.createMessage(MessageType.PlayerInput, ipt_type, prompt, error_msg, fltr)
        
        self.sendToClient(peer, msg)
        
        msg = self.requestMessage(MessageType.PlayerInput, client)
        if len(msg) >= 2:
            return msg[1]

    def getAddress(self) -> str:
        return self.address.host

    def getPort(self) -> int:
        return self.address.port

    def isServer(self) -> bool:
        return True

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    g = Game(loop)
    loop.run_until_complete(g.main())
