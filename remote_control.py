# remote_control.py
import time
from motor_control import MotorControl


def main():
    mc = MotorControl()
    print("Remote control started. Use WASD keys to control. Q to quit.")
    print("W: forward, S: backward, A: left, D: right, X: stop")

    try:
        while True:
            cmd = input("Command (w/s/a/d/x/q): ").strip().lower()
            if cmd == 'w':
                mc.set_linear_angular_velocities(0.5, 0.0)  # Forward
            elif cmd == 's':
                mc.set_linear_angular_velocities(-0.5, 0.0) # Backward
            elif cmd == 'a':
                mc.set_linear_angular_velocities(0.0, 1.0)  # Turn left
            elif cmd == 'd':
                mc.set_linear_angular_velocities(0.0, -1.0) # Turn right
            elif cmd == 'x':
                mc.set_linear_angular_velocities(0.0, 0.0)  # Stop
            elif cmd == 'q':
                print("Quitting...")
                break
            else:
                print("Unknown command.")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        mc.stop()

if __name__ == "__main__":
    main()