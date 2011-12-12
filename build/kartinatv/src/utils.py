#  Dreambox Enigma2 KartinaTV/RodnoeTV player! (by technic)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2, or (at your option) any later
# version.

import datetime
from operator import attrgetter

global Timezone
import time
Timezone = -time.timezone / 3600
print "[KartinaTV] dreambox timezone is GMT", Timezone

def tdSec(td):
	return td.days * 86400 + td.seconds
def tdmSec(td):
	#Add +1. Timer should wait for next event until event happed exactly.
	#Otherwise inaccuracy in round may lead to mistake.
	return td.days * 86400*1000 + td.seconds * 1000 + td.microseconds/1000 +1
def secTd(sec):
	return datetime.timedelta(sec / 86400, sec % 86400)
	
print "[KartinaTV] resetting time delta !!!"
time_delta = secTd(0)
	
def setSyncTime(time):
	global time_delta
	time_delta = time-datetime.datetime.now()
	print "[KartinaTV] set time delta to", tdSec(time_delta)

def syncTime():
	#print "[KartinaTV] time delta = ", tdSec(time_delta)
	return datetime.datetime.now() + time_delta

class EpgEntry():
	def __init__(self, name, t_start, t_end):
		self.name = name #all available info
		#no \n using in List
		name_split = self.name.split('\n')
		if name_split:
			self.progName = name_split[0]
		else:
			self.progName = name
		if len(name_split)>1:
			self.progDescr = name_split[1]
		else:
			self.progDescr = ''
		self.tstart = t_start
		self.tend = t_end
	
	#EPG is valid only if bouth tstart and tend specified!!!
	def isValid(self):
		return self.tstart and self.tend
	
	def startDefined(self):
		return self.tstart
	
	def getDuration(self):
		return tdSec(self.tend - self.tstart)

	duration = property(getDuration)
	
	def getTimePass(self, delta):
		now = syncTime()+secTd(delta)
		return tdSec(now-self.tstart)
	
	def getTimeLeft(self, delta):
		now = syncTime()+secTd(delta)
		return tdSec(self.tend-now)
	
	def getTimeLeftmsec(self, delta): #More accurancy, milliseconds
		now = syncTime()+secTd(delta)
		return tdmSec(self.tend-now)

	#programm is now and tstart and tend defined
	def isNow(self, delta): 
		if self.isValid():
			return self.tstart <= syncTime()+secTd(delta) and syncTime()+secTd(delta) < self.tend  
		return None
	
	def __str__(self):
		return ("%s -- %s %s") % (self.tstart.__str__(), self.tend.__str__(), self.progName)
	
	def __repr__(self):
		return self.__str__()

#TODO: thread safe @decorator for future backgroud epg loader ;)
class Channel(object):
	def __init__(self, name, group, num, gid, archive=0):
		self.name = name
		self.gid = gid
		self.num = num
		self.group = group
		self.archive = archive
		self.q = []
		self.lastUpdateFailed = False
	
	#EPG is valid only if bouth tstart and tend specified!!!
	#in this case hasSmth returns True
	
	def pushEpg(self, epg):
		self.pushEpgSorted([epg])
	
	def pushEpgSorted(self, epglist):
		#prepare list
		i = 0
		while i < len(epglist)-1:
			if epglist[i].tend is None:
				epglist[i].tend = epglist[i+1].tstart
			i += 1
		#push
		print "--------------------------------------------------"
		i = 0
		l_start = epglist[0].tstart
		l_end = epglist[-1].tstart
		print "+++", epglist, l_end
		
		while (i < len(self.q)) and (self.q[i].tstart < l_start):
			i += 1
#		if self.q[i].tend > l_start
#			self.q[i].tend = l_start
		ins_start = i
		
		while (i < len(self.q)) and (self.q[i].tstart <= l_end):
			i += 1
		ins_end = i
		
		if ins_start == ins_end:
			ins_end += 1
		print self.q
		self.q = self.q[:ins_start] + epglist + self.q[ins_end:]
		print "==>", ins_start, ins_end
		print self.q
	
	#TODO: add Heuristik. continue search from last position
	def findEpg(self, delta=0):
		i = 0
		while (i < len(self.q)) and not self.q[i].isNow(delta):
			i += 1
		if i == len(self.q):
			print "[KartinaTV] epg not found for", syncTime() + secTd(delta)
			return None
		else:
			return i
	
	def epgCurrent(self, delta=0):
		res = self.findEpg(delta)
		if res is None:
			return None
		else:
			return self.q[res]
	
	def epgNext(self, delta=0):
		i = self.findEpg(delta)
		if i is None:
			return None
		now = syncTime()+secTd(delta)
		curr = self.q[i]
		i += 1
		if (i < len(self.q)) and self.q[i].isValid():
			return self.q[i]
		return False
	
	def checkContinuity(self, a, b):
		i = a
		while i < b:
		  if self.q[i].tstart != self.q[i+1].tend:
			print "[KartinaTV] checkContinuity fail at", self.q[i].tstart
			return False
		return True
	
	def epgPeriod(self, tstart, tend):
		i = self.findEpg(tstart)
		j = self.findEpg(tend)
		if i and j and self.checkContinuity(i,j):
			return self.q[i:j]
		else:
			return False
	
	def epgDay(self, date):
		return self.epgPeriod(date, date + secTd(24*60*60))
	
	epg = property(fset = pushEpg)

class Bouquet():
	TYPE_SERVICE = 0
	TYPE_MENU = 1
	sort_keys_num = 10
	def __init__(self, type, name = None, key1 = None, key2 = None):
		self.type = type
		self.parent = None
		self.__content = []
		self.name = name
		self.key1 = key1
		self.key2 = key2
		self.sortedkey = -1 #XXX: Think more!!!
		self.index = 0
	
	def append(self, entry):
		entry.parent = self
		self.__content += [entry]
	
	def extend(self, boquet):
		for entry in bouquet.content:
			self.append(entry)
	
	def remove(self, id=None):
		if not id:
			id = self.index
		del self.__content[id]
		if self.index == len(self.content):
			self.index -= 1
	
	def sortByKey(self, keyn):
		print "[KartinaTV] sorting", self.name, keyn 
		if keyn == self.sortedkey: return
		if keyn == 1:
			self.__content.sort(key= attrgetter('key1'))
			self.sortedkey = keyn
		if keyn == 2:
			self.__content.sort(key= attrgetter('key2'))
			self.sortedkey = keyn
		self.index = 0
	
	def canMoveOneUp(self):
		return self.index > 0
	
	def moveOneUp(self):
		if self.canMoveOneUp():
			tmp = self.__content[self.index]
			self.__content[self.index] = self.__content[self.index-1]
			self.__content[self.index-1] =tmp
			self.index -= 1
	
	def canMoveOneDown(self):
		return self.index < len(self.__content)-1
	
	def moveOneDown(self):
		if self.canMoveOneDown():
			tmp = self.__content[self.index]
			self.__content[self.index] = self.__content[self.index+1]
			self.__content[self.index+1] =tmp
			self.index += 1
	
	def canInsertTo(self, pos):
		return 0 <= pos and pos <= len(self.__content)
	
	def insertTo(slef, pos):
		if self.canInsertTo(pos):
			self.__content.insert(pos, slef.__content[self.index])
			if pos <= self.index:
				self.__content.pop(self.index+1)
			else:
				self.__content.pos(self.index)
	
	def getContent(self):
		return self.__content
	
	content = property(getContent)
	
class BouquetManager():
	
	history_len = 10
	
	def __init__(self):
		self.root = Bouquet(Bouquet.TYPE_MENU, 'root')
		self.current = self.root
		self.history = []
		self.historyId = -1
		self.historyEnd = -1
		
		self.page = 1
		self.genres = []
		self.count = 0
		self.stype = 'last'
		self.query = ''
		self.saveDbselectVal()
	
	def saveDbselectVal(self):
		self._dbval_stored = (self.page, self.genres, self.count, self.stype, self.query)
	
	def restoreDbselectVal(self):
		(self.page, self.genres, self.count, self.stype, self.query) = self._dbval_stored
		
	def appendRoot(self, entry):
		self.root.append(entry)
	
	def goNext(self):
		self.goOut()
		self.current.index +=1
		if self.current.index == len(self.current.content):
			self.current.index = 0
		self.goIn()
		return self.getCurrent()
		
	def goPrev(self):
		self.goOut()
		self.current.index -=1
		if self.current.index == -1:
			self.current.index = len(self.current.content)-1
		self.goIn()
		return self.getCurrent()

	def goIn(self, index=None):
		if index != None:
			self.current.index = index
		if self.current.type == Bouquet.TYPE_MENU:
			self.current = self.current.content[self.current.index]
			self.current.index = 0
		print "[KartinaTV] bouquet In", self.current.name, self.current.index
		#return self.getList()
	
	def goOut(self):
		if self.current.parent:
			#FIXME: optimizations?? store parent_index in current?
			try:
				idx = self.current.parent.content.index(self.current)
			except ValueError:
				idx = 0
			self.current.parent.index = idx
			self.current = self.current.parent
			print "[KartinaTV] bouquet Out", self.current.name, self.current.index
		#return self.getList()
  
	def getList(self):
		return [x for x in self.current.content] #TODO: return only type and name
	
	def getCurrentSel(self):
		if len(self.current.content):
			return self.current.content[self.current.index]
	
	def getCurrent(self):
		return self.current.name
	
	def setIndex(self, index):
		self.current.index = index
	
	def getPath(self):
		x = self.current
		path = []
		while x != self.root:
			x = x.parent
			path = [x.index] + path
		return path
	
	def getPathName(self):
		x = self.current
		path = []
		while x != self.root:
			path = [x.name] + path
			x = x.parent
		return path
	
	def setPath(self, path, cid):
		for i in path:
			if i < len(self.current.content):
				self.goIn(i)
			else:
				break;
		if self.getCurrent() != cid:
			print "[KartinaTV] service not found in path!"
			self.current = self.root
			return False
		return True
	
	def historyNext(self):
		#print "[KartinaTV]", self.history, self.historyId
		if self.historyId < self.historyEnd and self.historyId > -1:
			self.historyId += 1
			h = self.history[self.historyId]
			self.current = self.root
			return self.setPath(h[0], h[1])
		else: return False
	
	def historyPrev(self):
		#print "[KartinaTV]", self.history, self.historyId
		if self.historyId > 0:
			self.historyId -= 1
			print "[KartinaTV]", self.historyId
			h = self.history[self.historyId]
			self.current = self.root
			return self.setPath(h[0], h[1])
		else: return False
	
	#FIXME: history stack is ugly!
	def historyAppend(self):
		h = (self.getPath(), self.getCurrent())
		self.historyId += 1
		if self.historyId == self.history_len:
			self.history.pop(0)
			self.historyId -= 1
		if len(self.history) > self.historyId:
			self.history[self.historyId] = h
		else:
			self.history += [h]
		self.historyEnd = self.historyId
		#print "[KartinaTV]", self.history, self.historyId		
		
class Video():
	def __init__(self, name):
		self.name = name
		self.year = None
		#TODO: set ALL fields!
		return

import re, htmlentitydefs

def unescapeEntities(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)

class APIException(Exception):
	def __init__(self, msg):
	  self.msg = msg
	def __str__(self):
	  return repr(self.msg)