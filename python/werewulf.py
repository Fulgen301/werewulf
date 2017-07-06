#!/usr/bin/env python3

from _thread import start_new_thread
from enum import IntEnum
import random

class Time(IntEnum):
	Day = 1
	Night = 2
	Both = 3

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
	
	def __init__(self, role : BasicRole, AI : bool = True, name : str = None) -> None:
		self.role = role
		self.AI = AI
		self.name = name if name else "Person"
	
	@classmethod
	def withNameFromList(cls, role : BasicRole, AI : bool = True, name_list : list = None) -> Person:
		name = None
		if name_list:
			random.shuffle(name_list)
			name = name_list.pop()
		
		return cls(role, AI, name)
	
	def kill(self) -> None:
		self.alive = False
		self.killable = False
	
	def __repr__(self) -> str:
		return self.name

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

class Roles(object):
	class Werewulf(BasicRole):
		time = Time.Night
		index = 5
		
		def __call__(self, game : Game, person : Person) -> bool:
			if game.current_victims != []: return True #WARNING: All roles which designate a victim must awake after the werewulves!
			
			available = list(filter(lambda x: x.alive and x.killable and x.role != self, game.people))
			
			if person.AI == False and person.alive:
				while True:
					victim = game.getPlayer(input("Enter a victim's name: \n> "), lambda x: x.alive and x.killable and type(x.role) != type(self))
					if victim:
						break
					else:
						print(f"Invalid victim. Maybe you tried killing yourself or another werewulf, or a protected person.")
			else:
				victim = random.choice(list(filter(lambda x: x.alive and x.killable and type(x.role) != type(self), game.people)))
			game.current_victims.append(victim)
			return True

		def hasWon(self, game : Game, time : int = None) -> bool:
			return len(list(game.getPlayersByFilter(lambda person: person.alive and person.role.__class__ != self.__class__))) <= 1

		def isValidVoteTarget(self, person : Person) -> bool:
			return person.role.__class__ != self.__class__ 
	
	class Villager(BasicRole):
		time = Time.Day
	
	class Witch(BasicRole):
		time = Time.Night
		index = 6
		potions = ["heal", "kill", "nothing"]

		def __call__(self, game : Game, person : Person) -> bool:
			if len(game.current_victims) == 0 or len(self.potions) == 1:
				return True

			if person.AI == False:
				victim = game.current_victims[0]
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
							game.current_victims.remove(victim)
							
						elif p == "kill":
							while True:
								second_victim = game.getPlayer(input(
										"Enter a victim's name. Available: {} \n> ".format(", ".join(str(i) for i in game.getPlayersByFilter(lambda p: p.alive and p.killable and p.role != self)))
									), lambda x: x != self and x.alive and x.killable)
								if second_victim:
									game.current_victims.append(second_victim)
									print(f"{second_victim} will be killed.")
									break
								else:
									print(f"Invalid victim. Maybe you tried killing yourself or a protected person.")

					if p != "nothing":
						self.potions.remove(p)
			else:
				victim = game.current_victims[0]
				ptn = random.choice(self.potions) if victim != self else "heal" # Always heal yourself if you are the victim
				if ptn == "heal":
					game.current_victims.remove(victim)
				elif ptn == "kill":
					for i in range(100):
						second_victim = random.choice(list(game.getPlayersByFilter(lambda p: p.alive and p.killable and p != self and p not in game.current_victims)))
						if second_victim:
							game.current_victims.append(second_victim)
							break

				if ptn != "nothing":
					self.potions.remove(ptn)
					
	
	class Seer(BasicRole):
		time = Time.Night
		index = 7

		def __call__(self, game : Game, person : Person) -> bool:
			if person.AI == False and person.alive:
				while True:
					victim = game.getPlayer(input("Enter the name of a person you want to see the role of: \n> "), lambda x: x.alive and x.killable and type(x.role) != type(self))
					if victim:
						print(f"The role of {victim} is {victim.role}.")
						break
					else:
						print(f"Invalid person.")

			return True

class Game(object):
	people = []
	player_count = 8
	player_role = None
	current_victims = []
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
	
	name_list = ["Alpha", "Beta", "Gamma", "Delta", "Max", "John", "Valentin", "Sarah", "Jane", "Ypsilon"]
	
	def __init__(self) -> None:
		self.showPlayerDialogue()
		self.setupAI()
		self.people.sort(key=lambda x: (x.role.index, x.AI))
	
	def showPlayerDialogue(self) -> None:
		print("Welcome to Werewulf.")
		
		#while True:
		#	try:
		#		self.chosen_set = self.role_sets[input(f"Please specify the used set.\nAvailable: {self.role_sets}\n> ")]
		#		break
		#	except KeyError:
		#		print("ERROR: This set does not exist.")
		self.chosen_set = self.role_sets["standard"]

		while True:
			role = input("Please specify the role you want to play.\nAvailable: {}, Spectator\n> ".format(", ".join(i.__name__ for i in self.chosen_set)))
			
			if role == "Spectator":
				break
			
			elif not getattr(Roles, role, None):
				print(f"ERROR: {role} is not a valid role.")
			else:
				self.people.append(Person(getattr(Roles, role)(), False, "Player"))
				break
		
		while True:
			try:
				self.player_count = int(input("Please specify the player count.\n> ")) - 1
				break
			except ValueError:
				print("ERROR: You did not enter a valid integer.")
				
	
	def setupAI(self) -> None:
		last = []
		for role in self.chosen_set:
			if type(self.chosen_set[role]) == list:
				while self.getRoleCount(role) < (self.player_count // self.chosen_set[role][1] * self.chosen_set[role][0]):
					self.people.append(Person.withNameFromList(role(), True, self.name_list))
			
			elif self.chosen_set[role] == None:
				last.append(role)
			
			elif type(self.chosen_set[role]) == int:
				while self.getRoleCount(role) < self.chosen_set[role]:
					self.people.append(Person.withNameFromList(role(), True, self.name_list))
		
		needed = max(self.player_count - len(self.people), 0)
		if not needed: return
		
		for role in last:
			for i in range(needed // len(last)):
				self.people.append(Person.withNameFromList(role(), True, self.name_list))
				
	
	def getRoleCount(self, role : BasicRole, time : int = None) -> int:
		"Returns the number of people with the role <role> and, if specified, the acting time <time>."
		return len(list(self.getPlayersByFilter(lambda person: person.role.__class__ == role and ((time and person.role.time & time) or True))))
	
	def getHumanPlayer(self) -> [Person, None]:
		"Returns the player "
		return self.getPlayerByFilter(lambda person: Person.AI == False)
	
	def getPlayer(self, name : str, fltr) -> [Person, None]:
		return self.getPlayerByFilter(lambda person: person.name == name and fltr(person))
	
	def getPlayerByFilter(self, fltr : filter) -> [Person, None]:
		for i in self.getPlayersByFilter(fltr):
			return i
	
	def getPlayersByFilter(self, fltr : filter) -> filter:
		return filter(fltr, self.people)
	
	def main(self) -> None:
		while self.night() and self.day(): pass
	
	def day(self) -> bool:
		self.accused = {}
		print("Night is over. The village awakes.", end="\n\n")
		if self.current_victims != []:
			for i in self.current_victims:
				print(f"{i}, a {i.role}, has been killed.")
				i.kill()

			self.current_victims = []
		else:
			print("No one has been killed.")

		print("Alive:", ", ".join(i.name for i in self.getPlayersByFilter(lambda x: x.alive)), end="\n\n")
		
		if self.checkFulfilled():
			return False
		
		player = self.getPlayerByFilter(lambda person: person.AI == False and person.alive)
		if player:
			while True:
				victim = self.getPlayer(input("Enter a victim's name: \n> "), lambda x: x.alive and x.killable and x != player)
				if victim:
					self.accused[victim] = 0
					break
				else:
					print(f"Invalid vote. Maybe you tried voting for your own death.")
		
		for i in range(2):
			self.accused[random.choice(list(self.getPlayersByFilter(lambda x: x.alive and x.killable and x not in self.accused)))] = 0
		
		while len(self.accused) > 1:
			
			print("Accused:", ", ".join(str(i) for i in self.accused))
			
			for person in self.getPlayersByFilter(lambda person: person.alive):
				shall_continue = False
				
				if person.AI:
					number = random.randint(0, len(self.accused) - 1)
					keys = list(self.accused.keys())
					while keys[number] == person or not person.role.isValidVoteTarget(keys[number]):
						if len(self.accused) == 1:	# only one victim
							shall_continue = True
							break
						
						number = random.randint(0, len(self.accused) - 1)
					
					if shall_continue: continue
					self.accused[keys[number]] += 1
				else:
					victim = self.getPlayer(
						input("Enter the name of the person you want to get killed. Available: {}\n> ".format(", ".join(str(i) for i in self.accused.keys()))), 
						lambda x: x.alive and x.killable)
					if victim and victim in self.accused:
						self.accused[victim] += 1
					else:
						print(f"Invalid vote.")
			
			items = list(self.accused.items())
			items.sort(key=lambda x: x[1], reverse=True)
			print("\nVotes:")
			for i in items:
				print(f"{i[0]}: {i[1]}")
			
			self.accused.pop(items[-1][0])
		
		victim = list(self.accused.items())[0][0]
		victim.kill()
		print(f"{victim}, a {victim.role}, has been killed.", end="\n\n")

		if self.checkFulfilled():
			return False
		
		print("The village sleeps.")
		return True
	
	def night(self):
		print("Night starts. Alive: " + ", ".join(i.name for i in self.getPlayersByFilter(lambda x: x.alive)), end="\n\n")
		
		for person in self.getPlayersByFilter(lambda person: person.alive and person.role.time & Time.Night):
			print(f"The {person.role} awakes.")
			person.role(self, person)
			print(f"The {person.role} sleeps.", end="\n\n")
		return True
	
	def checkFulfilled(self, time=None):
		res = list(self.getPlayersByFilter(lambda person: person.alive and person.role.hasWon(self, Time) and ((time and person.time & time) or True)))
		if len(res):
			print("{} have won.".format(", ".join(f"{i} ({i.role})" for i in res)))
			return True

if __name__ == "__main__":
	g = Game()
	g.main()