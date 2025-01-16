#!/usr/bin/env python3
def lineset(filename: str) -> set[str]:
  lines = open(filename).read().splitlines()
  return set(line.strip() for line in lines)
#print("\n".join(sorted(lineset('1.txt') - lineset('2.txt')))) # does a subtraction, ie, removes people from the list
print("\n".join(sorted(lineset('1.txt') & lineset('2.txt'))))
