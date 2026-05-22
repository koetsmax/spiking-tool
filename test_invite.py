import time
import keyboard

NAME_TO_INVITE = "gashers95"

# start the xbox app
print("Starting Xbox App")
keyboard.press_and_release("win")
time.sleep(2.5)
keyboard.write("xbox")
time.sleep(1.5)
keyboard.press_and_release("enter")
print("Xbox App Started")
time.sleep(30)
print("opening friends tab")
# 9 tabs to get to the friends tab #!! 11 on main pc
for i in range(11):
    keyboard.press_and_release("tab")
    time.sleep(0.5)
keyboard.press_and_release("enter")
print("Friends tab opened")
time.sleep(1)
print("searching for user")
# 2 tabs to get to the friend search bar
for i in range(2):
    keyboard.press_and_release("tab")
    time.sleep(0.5)
time.sleep(1)
# enter name of friend
keyboard.write(NAME_TO_INVITE)
time.sleep(1)
keyboard.press_and_release("enter")
print("User found")
time.sleep(6)
print("Getting to invite button")
# 5 tabs to get to user
for i in range(5):
    keyboard.press_and_release("tab")
    time.sleep(0.5)
# shift+f10 to emulate right click
keyboard.press_and_release("shift+f10")
time.sleep(1)
# do two reverse tabs
keyboard.press_and_release("shift+tab")
time.sleep(0.5)
keyboard.press_and_release("shift+tab")
time.sleep(0.5)
print("Inviting user")
keyboard.press_and_release("enter")
time.sleep(1)
print("User invited")
