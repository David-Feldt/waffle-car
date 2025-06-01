# remote_control.py
import time
import sys
import pygame
import threading
from motor_control import MotorControl

class ControllerInput:
    def __init__(self):
        self.current_command = None
        self.input_active = False
        self.running = True
        self.lock = threading.Lock()
        
        # Controller state
        self.left_stick_x = 0.0
        self.left_stick_y = 0.0
        self.right_stick_x = 0.0
        self.right_stick_y = 0.0
        self.l2_trigger = 0.0
        self.r2_trigger = 0.0
        self.buttons = {}
        
        # Initialize pygame
        pygame.init()
        pygame.joystick.init()
        self.controller = None
        
    def find_controller(self):
        """Find and initialize the first available controller"""
        joystick_count = pygame.joystick.get_count()
        
        if joystick_count == 0:
            print("No controllers detected!")
            return False
            
        # Use the first controller found
        self.controller = pygame.joystick.Joystick(0)
        self.controller.init()
        
        print(f"Controller connected: {self.controller.get_name()}")
        return True
        
    def controller_thread(self):
        """Dedicated thread for controller input monitoring"""
        try:
            while self.running:
                # Process pygame events
                pygame.event.pump()
                
                if self.controller:
                    with self.lock:
                        # Read analog sticks
                        if self.controller.get_numaxes() >= 2:
                            self.left_stick_x = self.controller.get_axis(0)
                            self.left_stick_y = self.controller.get_axis(1)
                        
                        if self.controller.get_numaxes() >= 4:
                            self.right_stick_x = self.controller.get_axis(2)
                            self.right_stick_y = self.controller.get_axis(3)
                        
                        # Read triggers (L2 and R2)
                        if self.controller.get_numaxes() >= 6:
                            self.l2_trigger = (self.controller.get_axis(4) + 1.0) / 2.0
                            self.r2_trigger = (self.controller.get_axis(5) + 1.0) / 2.0
                        
                        # Read buttons
                        for i in range(self.controller.get_numbuttons()):
                            self.buttons[i] = self.controller.get_button(i)
                        
                        # Determine current command based on controller input
                        self.current_command = self._determine_command()
                        
                time.sleep(0.01)  # 10ms update rate
                
        except Exception as e:
            print(f"Controller thread error: {e}")
            self.running = False
    
    def _determine_command(self):
        """Determine the current command based on controller input"""
        DEADZONE = 0.15
        TRIGGER_DEADZONE = 0.05
        
        # Check for quit button (Options button)
        if self.buttons.get(9, False):
            return 'q'
        
        # Check for emergency stop (X/Cross button)
        if self.buttons.get(0, False):
            return 'x'
        
        # Check triggers first (highest priority)
        if self.r2_trigger > TRIGGER_DEADZONE:
            self.input_active = True
            return 'w'  # Forward
        elif self.l2_trigger > TRIGGER_DEADZONE:
            self.input_active = True
            return 's'  # Backward
        
        # Check right stick (medium priority)
        elif abs(self.right_stick_x) > DEADZONE or abs(self.right_stick_y) > DEADZONE:
            self.input_active = True
            if abs(self.right_stick_y) > abs(self.right_stick_x):
                return 'w' if self.right_stick_y < -DEADZONE else 's'
            else:
                return 'd' if self.right_stick_x > DEADZONE else 'a'
        
        # Check left stick (lowest priority)
        elif abs(self.left_stick_x) > DEADZONE or abs(self.left_stick_y) > DEADZONE:
            self.input_active = True
            if abs(self.left_stick_y) > abs(self.left_stick_x):
                return 'w' if self.left_stick_y < -DEADZONE else 's'
            else:
                return 'd' if self.left_stick_x > DEADZONE else 'a'
        
        # No significant input
        else:
            self.input_active = False
            return None
    
    def get_current_command(self):
        """Get the currently active command (thread-safe)"""
        with self.lock:
            return self.current_command if self.input_active else None
    
    def is_input_active(self):
        """Check if any input is currently active (thread-safe)"""
        with self.lock:
            return self.input_active
    
    def get_analog_values(self):
        """Get current analog values for proportional control"""
        with self.lock:
            return {
                'left_stick_x': self.left_stick_x,
                'left_stick_y': self.left_stick_y,
                'right_stick_x': self.right_stick_x,
                'right_stick_y': self.right_stick_y,
                'l2_trigger': self.l2_trigger,
                'r2_trigger': self.r2_trigger
            }
    
    def stop(self):
        """Stop the controller monitoring thread"""
        self.running = False
        if self.controller:
            self.controller.quit()
        pygame.quit()

def main():
    mc = MotorControl()
    controller_input = ControllerInput()
    
    print("Threaded hold-to-move Controller control started!")
    print("Connecting to controller...")
    
    # Try to find and connect to controller
    if not controller_input.find_controller():
        print("Failed to find controller. Make sure it's connected and try again.")
        return
    
    print("Controller Controls:")
    print("Left Stick: WASD-style movement")
    print("Right Stick: Direct movement control")
    print("R2 Trigger: Forward")
    print("L2 Trigger: Backward")
    print("X Button: Emergency stop")
    print("Options Button: Quit")
    print("You must HOLD the controls to keep moving!")
    
    # Start controller monitoring thread
    controller_thread = threading.Thread(target=controller_input.controller_thread, daemon=True)
    controller_thread.start()
    
    last_command = None
    
    # Current velocities for smooth transitions
    current_linear = 0.0
    current_angular = 0.0
    
    # Target velocities
    target_linear = 0.0
    target_angular = 0.0
    
    # Smoothing factor (0.1 = very smooth, 0.9 = very responsive)
    SMOOTHING = 0.3
    
    try:
        while True:
            cmd = controller_input.get_current_command()
            analog_values = controller_input.get_analog_values()
            
            if cmd:
                # Get intensity from analog values for proportional control
                intensity = 1.0  # Default intensity
                
                if cmd == 'w':
                    if analog_values['r2_trigger'] > 0.05:
                        intensity = analog_values['r2_trigger']
                        if last_command != 'w':
                            print(f"Forward (R2 trigger: {intensity:.2f})")
                    elif abs(analog_values['right_stick_y']) > 0.15:
                        intensity = abs(analog_values['right_stick_y'])
                        if last_command != 'w':
                            print(f"Forward (Right stick: {intensity:.2f})")
                    elif abs(analog_values['left_stick_y']) > 0.15:
                        intensity = abs(analog_values['left_stick_y'])
                    if last_command != 'w':
                            print(f"Forward (Left stick: {intensity:.2f})")
                    
                    target_linear = -4.0 * intensity
                    target_angular = 0.0
                    last_command = 'w'
                    
                elif cmd == 's':
                    if analog_values['l2_trigger'] > 0.05:
                        intensity = analog_values['l2_trigger']
                        if last_command != 's':
                            print(f"Backward (L2 trigger: {intensity:.2f})")
                    elif abs(analog_values['right_stick_y']) > 0.15:
                        intensity = abs(analog_values['right_stick_y'])
                        if last_command != 's':
                            print(f"Backward (Right stick: {intensity:.2f})")
                    elif abs(analog_values['left_stick_y']) > 0.15:
                        intensity = abs(analog_values['left_stick_y'])
                    if last_command != 's':
                            print(f"Backward (Left stick: {intensity:.2f})")
                    
                    target_linear = 4.0 * intensity
                    target_angular = 0.0
                    last_command = 's'
                    
                elif cmd == 'a':
                    if abs(analog_values['right_stick_x']) > 0.15:
                        intensity = abs(analog_values['right_stick_x'])
                        if last_command != 'a':
                            print(f"Left (Right stick: {intensity:.2f})")
                    elif abs(analog_values['left_stick_x']) > 0.15:
                        intensity = abs(analog_values['left_stick_x'])
                    if last_command != 'a':
                            print(f"Left (Left stick: {intensity:.2f})")
                    
                    target_linear = 0.0
                    target_angular = -8.0 * intensity
                    last_command = 'a'
                    
                elif cmd == 'd':
                    if abs(analog_values['right_stick_x']) > 0.15:
                        intensity = abs(analog_values['right_stick_x'])
                        if last_command != 'd':
                            print(f"Right (Right stick: {intensity:.2f})")
                    elif abs(analog_values['left_stick_x']) > 0.15:
                        intensity = abs(analog_values['left_stick_x'])
                    if last_command != 'd':
                            print(f"Right (Left stick: {intensity:.2f})")
                    
                    target_linear = 0.0
                    target_angular = 8.0 * intensity
                    last_command = 'd'
                    
                elif cmd == 'x':
                    print("Emergency stop")
                    target_linear = 0.0
                    target_angular = 0.0
                    last_command = 'x'
                    
                elif cmd == 'q':
                    print("Quitting...")
                    break
                    
            else:
                # No input - stop if we were moving
                if last_command in ['w', 's', 'a', 'd']:
                    if target_linear != 0.0 or target_angular != 0.0:
                        print("Controls released - stopping")
                    target_linear = 0.0
                    target_angular = 0.0
                    last_command = None
            
            # Smooth velocity transitions
            current_linear += (target_linear - current_linear) * SMOOTHING
            current_angular += (target_angular - current_angular) * SMOOTHING
            
            # Send motor commands
            mc.set_linear_angular_velocities(current_linear, current_angular)
            
            time.sleep(0.005)  # 5ms loop for smooth control
            
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        controller_input.stop()
        mc.stop()
        print("Motors stopped and controller disconnected.")

if __name__ == "__main__":
    main()