# controller_control.py
import time
import pygame
import sys
import threading
from motor_control import MotorControl

class ControllerManager:
    def __init__(self):
        self.controller = None
        self.running = True
        self.lock = threading.Lock()
        
        # Controller state
        self.left_stick_x = 0.0
        self.left_stick_y = 0.0
        self.right_stick_x = 0.0
        self.right_stick_y = 0.0
        self.l2_trigger = 0.0
        self.r2_trigger = 0.0
        
        # Button states
        self.buttons = {}
        
        # Initialize pygame
        pygame.init()
        pygame.joystick.init()
        
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
        print(f"Number of axes: {self.controller.get_numaxes()}")
        print(f"Number of buttons: {self.controller.get_numbuttons()}")
        print(f"Number of hats: {self.controller.get_numhats()}")
        
        return True
        
    def controller_thread(self):
        """Dedicated thread for controller input monitoring"""
        try:
            while self.running:
                # Process pygame events
                pygame.event.pump()
                
                if self.controller:
                    with self.lock:
                        # Read analog sticks (normalize from -1.0 to 1.0)
                        if self.controller.get_numaxes() >= 2:
                            self.left_stick_x = self.controller.get_axis(0)
                            self.left_stick_y = self.controller.get_axis(1)
                        
                        if self.controller.get_numaxes() >= 4:
                            self.right_stick_x = self.controller.get_axis(2)
                            self.right_stick_y = self.controller.get_axis(3)
                        
                        # Read triggers (L2 and R2)
                        if self.controller.get_numaxes() >= 6:
                            # On DualShock 4, L2 is usually axis 4, R2 is axis 5
                            self.l2_trigger = (self.controller.get_axis(4) + 1.0) / 2.0  # Convert from -1,1 to 0,1
                            self.r2_trigger = (self.controller.get_axis(5) + 1.0) / 2.0  # Convert from -1,1 to 0,1
                        
                        # Read buttons
                        for i in range(self.controller.get_numbuttons()):
                            self.buttons[i] = self.controller.get_button(i)
                
                time.sleep(0.01)  # 10ms update rate
                
        except Exception as e:
            print(f"Controller thread error: {e}")
            self.running = False
    
    def get_controller_state(self):
        """Get current controller state (thread-safe)"""
        with self.lock:
            return {
                'left_stick_x': self.left_stick_x,
                'left_stick_y': self.left_stick_y,
                'right_stick_x': self.right_stick_x,
                'right_stick_y': self.right_stick_y,
                'l2_trigger': self.l2_trigger,
                'r2_trigger': self.r2_trigger,
                'buttons': self.buttons.copy()
            }
    
    def stop(self):
        """Stop the controller monitoring"""
        self.running = False
        if self.controller:
            self.controller.quit()
        pygame.quit()

def apply_deadzone(value, deadzone=0.1):
    """Apply deadzone to analog stick values"""
    if abs(value) < deadzone:
        return 0.0
    # Scale the remaining range to 0-1
    if value > 0:
        return (value - deadzone) / (1.0 - deadzone)
    else:
        return (value + deadzone) / (1.0 - deadzone)

def main():
    mc = MotorControl()
    controller_mgr = ControllerManager()
    
    print("DualShock 4 Robot Control Started!")
    print("Connecting to controller...")
    
    # Try to find and connect to controller
    if not controller_mgr.find_controller():
        print("Failed to find controller. Make sure it's connected and try again.")
        return
    
    print("\nController Controls:")
    print("Left Stick: Tank-style steering (Y-axis forward/back, X-axis turn)")
    print("Right Stick: Direct linear/angular control")
    print("L2 Trigger: Reverse")
    print("R2 Trigger: Forward")
    print("X Button (Cross): Emergency stop")
    print("Options Button: Quit")
    print("Hold buttons/sticks to move, release to stop")
    
    # Start controller monitoring thread
    controller_thread = threading.Thread(target=controller_mgr.controller_thread, daemon=True)
    controller_thread.start()
    
    # Control variables
    current_linear = 0.0
    current_angular = 0.0
    target_linear = 0.0
    target_angular = 0.0
    
    # Smoothing factor (0.1 = very smooth, 0.9 = very responsive)
    SMOOTHING = 0.3
    
    # Speed scaling factors
    MAX_LINEAR_SPEED = 4.0
    MAX_ANGULAR_SPEED = 8.0
    
    # Deadzone for analog sticks
    STICK_DEADZONE = 0.15
    TRIGGER_DEADZONE = 0.05
    
    last_control_mode = None
    
    try:
        while True:
            state = controller_mgr.get_controller_state()
            
            # Check for quit button (Options button is usually button 9 on DualShock 4)
            if state['buttons'].get(9, False):  # Options button
                print("Options button pressed - quitting...")
                break
            
            # Emergency stop (X/Cross button is usually button 0)
            if state['buttons'].get(0, False):  # X/Cross button
                if last_control_mode != 'emergency_stop':
                    print("Emergency stop activated!")
                target_linear = 0.0
                target_angular = 0.0
                last_control_mode = 'emergency_stop'
            else:
                # Apply deadzone to stick inputs
                left_x = apply_deadzone(state['left_stick_x'], STICK_DEADZONE)
                left_y = apply_deadzone(-state['left_stick_y'], STICK_DEADZONE)  # Invert Y
                right_x = apply_deadzone(state['right_stick_x'], STICK_DEADZONE)
                right_y = apply_deadzone(-state['right_stick_y'], STICK_DEADZONE)  # Invert Y
                
                # Apply deadzone to triggers
                l2 = state['l2_trigger'] if state['l2_trigger'] > TRIGGER_DEADZONE else 0.0
                r2 = state['r2_trigger'] if state['r2_trigger'] > TRIGGER_DEADZONE else 0.0
                
                # Determine control mode based on what's being used
                control_mode = None
                
                # Priority 1: Triggers (simple forward/reverse)
                if l2 > 0 or r2 > 0:
                    if l2 > r2:
                        target_linear = l2 * MAX_LINEAR_SPEED  # Reverse
                        target_angular = 0.0
                        control_mode = 'trigger_reverse'
                    else:
                        target_linear = -r2 * MAX_LINEAR_SPEED  # Forward
                        target_angular = 0.0
                        control_mode = 'trigger_forward'
                
                # Priority 2: Right stick (direct linear/angular control)
                elif abs(right_x) > 0 or abs(right_y) > 0:
                    target_linear = -right_y * MAX_LINEAR_SPEED
                    target_angular = right_x * MAX_ANGULAR_SPEED
                    control_mode = 'right_stick'
                
                # Priority 3: Left stick (tank-style control)
                elif abs(left_x) > 0 or abs(left_y) > 0:
                    # Tank-style: Y for forward/back, X for turning
                    target_linear = -left_y * MAX_LINEAR_SPEED
                    target_angular = left_x * MAX_ANGULAR_SPEED
                    control_mode = 'left_stick'
                
                # No input - stop
                else:
                    target_linear = 0.0
                    target_angular = 0.0
                    control_mode = 'idle'
                
                # Print control mode changes
                if control_mode != last_control_mode and control_mode != 'idle':
                    if control_mode == 'trigger_forward':
                        print(f"Trigger control: Forward ({r2:.2f})")
                    elif control_mode == 'trigger_reverse':
                        print(f"Trigger control: Reverse ({l2:.2f})")
                    elif control_mode == 'right_stick':
                        print(f"Right stick control: Linear={right_y:.2f}, Angular={right_x:.2f}")
                    elif control_mode == 'left_stick':
                        print(f"Left stick control: Linear={left_y:.2f}, Angular={left_x:.2f}")
                elif control_mode == 'idle' and last_control_mode != 'idle':
                    print("Controls released - stopping")
                
                last_control_mode = control_mode
            
            # Smooth velocity transitions
            current_linear += (target_linear - current_linear) * SMOOTHING
            current_angular += (target_angular - current_angular) * SMOOTHING
            
            # Send motor commands
            mc.set_linear_angular_velocities(current_linear, current_angular)
            
            time.sleep(0.01)  # 10ms control loop
            
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        controller_mgr.stop()
        mc.stop()
        print("Motors stopped and controller disconnected.")

if __name__ == "__main__":
    main() 