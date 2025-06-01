# remote_control.py
import time
import sys
import select
import termios
import tty
import threading
from motor_control import MotorControl

class KeyboardController:
    def __init__(self):
        self.current_key = None
        self.key_pressed = False
        self.running = True
        self.lock = threading.Lock()
        
    def keyboard_thread(self):
        """Dedicated thread for keyboard input monitoring"""
        # Set terminal to raw mode for this thread
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        
        try:
            while self.running:
                if select.select([sys.stdin], [], [], 0.01) == ([sys.stdin], [], []):
                    char = sys.stdin.read(1)
                    with self.lock:
                        self.current_key = char.lower()
                        self.key_pressed = True
                else:
                    # No key pressed
                    with self.lock:
                        self.key_pressed = False
                        
                time.sleep(0.001)  # Very small delay to prevent excessive CPU usage
        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def get_current_key(self):
        """Get the currently pressed key (thread-safe)"""
        with self.lock:
            return self.current_key if self.key_pressed else None
    
    def is_key_pressed(self):
        """Check if any key is currently pressed (thread-safe)"""
        with self.lock:
            return self.key_pressed
    
    def stop(self):
        """Stop the keyboard monitoring thread"""
        self.running = False

def main():
    mc = MotorControl()
    keyboard_ctrl = KeyboardController()
    
    print("Threaded hold-to-move WASD control started!")
    print("Hold W: forward, Hold S: backward, Hold A: left, Hold D: right")
    print("Release key to stop, Q: quit")
    print("You must HOLD the keys down to keep moving!")
    
    # Start keyboard monitoring thread
    keyboard_thread = threading.Thread(target=keyboard_ctrl.keyboard_thread, daemon=True)
    keyboard_thread.start()
    
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
            cmd = keyboard_ctrl.get_current_key()
            
            if cmd:
                if cmd == 'w':
                    if last_command != 'w':
                        print("Forward (hold to continue)")
                    target_linear = -4.0
                    target_angular = 0.0
                    last_command = 'w'
                elif cmd == 's':
                    if last_command != 's':
                        print("Backward (hold to continue)")
                    target_linear = 4.0
                    target_angular = 0.0
                    last_command = 's'
                elif cmd == 'a':
                    if last_command != 'a':
                        print("Left (hold to continue)")
                    target_linear = 0.0
                    target_angular = -8.0
                    last_command = 'a'
                elif cmd == 'd':
                    if last_command != 'd':
                        print("Right (hold to continue)")
                    target_linear = 0.0
                    target_angular = 8.0
                    last_command = 'd'
                elif cmd == 'x':
                    print("Manual stop")
                    target_linear = 0.0
                    target_angular = 0.0
                    last_command = 'x'
                elif cmd == 'q':
                    print("Quitting...")
                    break
                elif cmd == '\x03':  # Ctrl+C
                    break
            else:
                # No key pressed - stop if we were moving
                if last_command in ['w', 's', 'a', 'd']:
                    if target_linear != 0.0 or target_angular != 0.0:
                        print("Key released - stopping")
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
        keyboard_ctrl.stop()
        mc.stop()
        print("Motors stopped and keyboard thread terminated.")

if __name__ == "__main__":
    main()