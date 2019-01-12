import random


def scrambleCharacter(c):
	a1 = 65
	a2 = 90
	b1 = 97
	b2 = 122
	c1 = 48
	c2 = 57

	ci = ord(c)

	if a1 <= ci <= a2:
		c = chr(random.randint(a1, a2))
	elif b1 <= ci <= b2:
		c = chr(random.randint(b1, b2))
	elif c1 <= ci <= c2:
		c = chr(random.randint(c1, c2))

	return c


def scrambleAddress(addr):
	p1 = addr.find(":")

	addrOut = addr[:p1]
	for c in addr[p1:]:
		addrOut += scrambleCharacter(c)

	return addrOut
