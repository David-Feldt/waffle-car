import pygame
import time

pygame.init()
pygame.joystick.init()

joystick_count = pygame.joystick.get_count()
if joystick_count == 0:
    print("No joystick detected.")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()

print(f"Connected to: {joystick.get_name()}")

while True:
    pygame.event.pump()
    
    print("\n--- AXES ---")
    for i in range(joystick.get_numaxes()):
        print(f"Axis {i}: {joystick.get_axis(i):.2f}")

    print("--- BUTTONS ---")
    for i in range(joystick.get_numbuttons()):
        print(f"Button {i}: {joystick.get_button(i)}")

    print("--- HATS (D-pad) ---")
    for i in range(joystick.get_numhats()):
        print(f"Hat {i}: {joystick.get_hat(i)}")
    
    time.sleep(0.3)
