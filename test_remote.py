import os
import pygame
import time
import signal
import sys

# Fix for headless environments (SSH, no GUI)
os.environ["SDL_VIDEODRIVER"] = "dummy"

class TestRemoteController:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        
        self.joystick = None
        self.running = True
        
        # Control parameters
        self.deadzone = 0.1  # Ignore joystick values below this threshold
        self.max_linear_speed = 4.0  # Maximum linear speed in m/s
        self.max_angular_speed = 8.0  # Maximum angular speed in rad/s
        self.speed_multiplier = 1.0  # Normal speed multiplier
        self.turbo_multiplier = 2.0  # Turbo speed multiplier
        
        # Safety and monitoring
        self.last_activity_time = time.time()
        self.watchdog_timeout = 1.0  # seconds without input before stopping
        self.connection_active = False
        self.emergency_stop_active = False
        
        # Control loop timing
        self.control_loop_rate = 0.1  # 100ms for testing
        
        print("Test Remote Controller initialized")
        print(f"Deadzone: {self.deadzone}")
        print(f"Max speeds - Linear: {self.max_linear_speed} m/s, Angular: {self.max_angular_speed} rad/s")
        print(f"Watchdog timeout: {self.watchdog_timeout} seconds")
        
    def apply_deadzone(self, value):
        """Apply deadzone to joystick values to prevent drift"""
        if abs(value) < self.deadzone:
            return 0.0
        return value
    
    def check_joystick_connection(self):
        """Check and initialize joystick connection"""
        if self.joystick is None or not self.joystick.get_init():
            pygame.joystick.quit()
            pygame.joystick.init()
            
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.connection_active = True
                self.last_activity_time = time.time()
                print(f"Joystick connected: {self.joystick.get_name()}")
                print(f"Number of axes: {self.joystick.get_numaxes()}")
                print(f"Number of buttons: {self.joystick.get_numbuttons()}")
                return True
            else:
                if self.connection_active:
                    print("Joystick disconnected")
                self.connection_active = False
                return False
        return True
    
    def send_stop_command(self, reason):
        """Send stop command (test version)"""
        print(f"STOP: {reason}")
    
    def emergency_stop(self, reason):
        """Emergency stop (test version)"""
        print(f"EMERGENCY STOP: {reason}")
        self.emergency_stop_active = True
    
    def process_joystick_input(self):
        """Process joystick input and return target velocities"""
        if not self.joystick or not self.joystick.get_init():
            return 0.0, 0.0, False
        
        # Handle pygame events for hotplug detection
        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEREMOVED:
                if hasattr(event, 'instance_id') and self.joystick and event.instance_id == self.joystick.get_instance_id():
                    print("Joystick removed via pygame event")
                    self.send_stop_command("Joystick removed")
                    self.joystick = None
                    self.connection_active = False
                    return 0.0, 0.0, False
            elif event.type == pygame.JOYDEVICEADDED:
                if not self.joystick:
                    print("New joystick detected via pygame event")
                    self.check_joystick_connection()
        
        pygame.event.pump()
        
        # Get joystick input
        # Left stick Y-axis for forward/backward (inverted)
        linear_input = -self.joystick.get_axis(1)
        # Right stick X-axis for left/right turning
        angular_input = self.joystick.get_axis(2)
        
        # Apply deadzone
        linear_input = self.apply_deadzone(linear_input)
        angular_input = self.apply_deadzone(angular_input)
        
        # Check for emergency stop button (Button B - typically button 1)
        if self.joystick.get_button(1):
            self.emergency_stop("Emergency stop button pressed")
            return 0.0, 0.0, False
        
        # Check for turbo mode (Right bumper - typically button 7)
        turbo_active = self.joystick.get_button(7)
        current_multiplier = self.turbo_multiplier if turbo_active else self.speed_multiplier
        
        if turbo_active:
            print("TURBO MODE ACTIVE")
        
        # Calculate target velocities
        target_linear = linear_input * self.max_linear_speed * current_multiplier
        target_angular = angular_input * self.max_angular_speed * current_multiplier
        
        # Check if we have any input
        has_input = (abs(linear_input) > 0.0 or abs(angular_input) > 0.0)
        
        if has_input:
            self.last_activity_time = time.time()
            print(f"Input: Linear={target_linear:.2f}, Angular={target_angular:.2f}")
        
        # Debug: Show all button states
        buttons_pressed = []
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i):
                buttons_pressed.append(i)
        if buttons_pressed:
            print(f"Buttons pressed: {buttons_pressed}")
        
        return target_linear, target_angular, has_input
    
    def watchdog_check(self):
        """Check if we've lost communication and should stop"""
        current_time = time.time()
        time_since_activity = current_time - self.last_activity_time
        
        if time_since_activity > self.watchdog_timeout and self.connection_active:
            self.send_stop_command(f"Watchdog timeout: {time_since_activity:.1f}s without input")
            return False
        return True
    
    def control_loop(self):
        """Main control loop"""
        print("Starting test control loop...")
        print("Controls:")
        print("  Left stick Y-axis: Forward/Backward")
        print("  Right stick X-axis: Left/Right turn")
        print("  Right bumper: Turbo mode")
        print("  Button B: Emergency stop")
        print("  Ctrl+C: Quit")
        print("\nWaiting for joystick connection...")
        
        last_connection_check = time.time()
        connection_check_interval = 1.0  # Check connection every second
        
        try:
            while self.running:
                current_time = time.time()
                
                # Periodic connection check
                if current_time - last_connection_check > connection_check_interval:
                    self.check_joystick_connection()
                    last_connection_check = current_time
                
                # Skip control if emergency stop is active
                if self.emergency_stop_active:
                    print("Emergency stop active - press Ctrl+C to quit")
                    time.sleep(self.control_loop_rate)
                    continue
                
                # Watchdog check
                if not self.watchdog_check():
                    time.sleep(self.control_loop_rate)
                    continue
                
                # Process joystick input
                target_linear, target_angular, has_input = self.process_joystick_input()
                
                # Control loop timing
                time.sleep(self.control_loop_rate)
                
        except KeyboardInterrupt:
            print("\nShutdown requested by user")
        except Exception as e:
            print(f"Unexpected error in control loop: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        print("Shutting down test remote controller...")
        self.running = False
        
        # Clean up pygame
        try:
            pygame.quit()
        except Exception as e:
            print(f"Error cleaning up pygame: {e}")
        
        print("Test remote controller shutdown complete")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}")
    global controller
    if 'controller' in globals():
        controller.shutdown()
    sys.exit(0)

def main():
    global controller
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        controller = TestRemoteController()
        controller.control_loop()
    except Exception as e:
        print(f"Fatal error: {e}")
        if 'controller' in globals():
            controller.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main() 