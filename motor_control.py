import json
import logging
import os
import time
import traceback
import signal
import sys
import math

import numpy as np

import constants as CFG
from odrive_uart import ODriveUART, reset_odrive

MOTOR_TURNS_TO_LINEAR_POS = CFG.ROBOT_WHEEL_RADIUS_M * 2 * np.pi
RPM_TO_METERS_PER_SECOND = CFG.ROBOT_WHEEL_RADIUS_M * 2 * np.pi / 60

# Fallback for get_motor_directions if not defined elsewhere
try:
    get_motor_directions
except NameError:
    def get_motor_directions():
        import constants as CFG
        return CFG.MOTOR_CONTROL_LEFT_MOTOR_DIR, CFG.MOTOR_CONTROL_RIGHT_MOTOR_DIR

class MotorControl:
    def __init__(self):
        # Set up basic logging
        self.logger = logging.getLogger("motor_control")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Initialize idle state tracking
        self.is_idle = False

        try:
            self.left_motor_dir, self.right_motor_dir = get_motor_directions()
        except Exception as e:
            print(f"Error getting motor directions from JSON file, using constants from config instead: {e}")
            self.left_motor_dir, self.right_motor_dir = CFG.MOTOR_CONTROL_LEFT_MOTOR_DIR, CFG.MOTOR_CONTROL_RIGHT_MOTOR_DIR

        
        # Initialize motors
        self.reset_and_initialize_motors()

        self.cycle_count = 0

    def start_motors_velocity_mode(self):
        """Initialize and start motors in velocity mode"""
        print("Starting motors in velocity mode...")
        self.motor_controller.start_left()
        self.motor_controller.start_right()
        print("Motors started, enabling velocity mode...")
        self.motor_controller.enable_velocity_mode_left()
        self.motor_controller.enable_velocity_mode_right()
        
        # Configure for immediate response instead of ramping
        print("Configuring for maximum acceleration...")
        
        # Option 1: Try completely disabling velocity ramping first (most immediate)
        self.motor_controller.disable_velocity_ramping_left()
        self.motor_controller.disable_velocity_ramping_right()
        
        # Option 2: If above causes issues, can fall back to high ramp rate
        # self.motor_controller.config_velocity_ramp_left(1000.0)
        # self.motor_controller.config_velocity_ramp_right(1000.0)
        
        # Increase current limits for more torque during acceleration
        # Adjust these values based on your motor specifications
        self.motor_controller.set_current_limit(self.motor_controller.left_axis, 40.0)
        self.motor_controller.set_current_limit(self.motor_controller.right_axis, 40.0)
        
        # Get current ramp rates to verify
        left_ramp = self.motor_controller.get_velocity_ramp(self.motor_controller.left_axis)
        right_ramp = self.motor_controller.get_velocity_ramp(self.motor_controller.right_axis)
        print(f"Velocity ramp rates - Left: {left_ramp}, Right: {right_ramp}")
        
        print("Velocity mode enabled for both motors with max acceleration")
        
        # Dump complete motor configuration for verification
        print("\nDumping complete motor configuration for verification:")
        self.dump_motor_config()

    def start_motors_torque_mode(self):
        """Initialize and start motors in torque mode"""
        print("Starting motors in torque mode...")
        self.motor_controller.start_left()
        self.motor_controller.start_right()
        print("Motors started, enabling torque mode...")
        self.motor_controller.enable_torque_mode_left()
        self.motor_controller.enable_torque_mode_right()
        print("Torque mode enabled for both motors")

    def reset_and_initialize_motors(self, torque_mode=False):
        """Reset the ODrive and re-initialize the motors."""
        print("\n=== Starting motor reset and initialization ===")
        print(f"Resetting ODrive (torque_mode={torque_mode})...")
        self.reset_odrive()
        time.sleep(1)  # Give ODrive time to reset
        try:
            print(f"Initializing motor controller on port {CFG.MOTOR_CONTROL_SERIAL_PORT}")
            print(f"Motor directions - Left: {self.left_motor_dir}, Right: {self.right_motor_dir}")
            self.motor_controller = ODriveUART(CFG.MOTOR_CONTROL_SERIAL_PORT,
                                               left_axis=CFG.MOTOR_CONTROL_LEFT_MOTOR_AXIS,
                                               right_axis=CFG.MOTOR_CONTROL_RIGHT_MOTOR_AXIS,
                                               dir_left=self.left_motor_dir,
                                               dir_right=self.right_motor_dir)
            print("Clearing any existing errors...")
            self.motor_controller.clear_errors_left()
            self.motor_controller.clear_errors_right()
            if torque_mode:
                self.start_motors_torque_mode()
            else:
                self.start_motors_velocity_mode()
            print("Motors re-initialized successfully.")
        except Exception as e:
            print(f"ERROR re-initializing motors: {e}")
            print("Detailed traceback:")
            traceback.print_exc()

    def reset_odrive(self):
        """
        Reset the ODrive controller.
        """
        reset_odrive()
        time.sleep(0.5)

    def get_left_motor_velocity(self):
        """Get the current velocity of the left motor."""
        try:
            l_pos_m, l_vel_mps = self.motor_controller.get_pos_vel_left()

            l_vel_mps = l_vel_mps * RPM_TO_METERS_PER_SECOND

            return l_vel_mps
        except Exception as e:
            print('Motor controller error:', e)
            self.reset_and_initialize_motors()
            return 0.0
    
    def get_right_motor_velocity(self):
        """Get the current velocity of the right motor."""
        try:
            r_pos_m, r_vel_mps = self.motor_controller.get_pos_vel_right()

            r_vel_mps = r_vel_mps * RPM_TO_METERS_PER_SECOND

            return r_vel_mps
        except Exception as e:
            print('Motor controller error:', e)
            self.reset_and_initialize_motors()
            return 0.0

    def set_linear_angular_velocities(self, velocity_target_mps=0.0, yaw_rate_target_rad_s=0.0):
        """
        Set the linear and angular velocities of the robot.

        :param velocity_target_mps: Target velocity in meters per second.
        :param yaw_rate_target_rad_s: Target yaw rate in radians per second.
        """
        # self.logger.info(f"Setting velocities - Linear: {velocity_target_mps:.3f} m/s, Angular: {yaw_rate_target_rad_s:.3f} rad/s")
        try:            
            # Special case for zero velocity and zero yaw - complete stop
            if velocity_target_mps == 0.0 and yaw_rate_target_rad_s == 0.0:
                self.logger.info("Zero velocity and yaw detected - stopping all movement")
                self.stop()

                # self.motor_controller.set_speed_rpm_left(0)
                # self.motor_controller.set_speed_rpm_right(0)
                # return
            # else:
            #     self.motor_controller.enable_velocity_mode_left()
            #     self.motor_controller.enable_velocity_mode_right()
            if self.is_idle:
                self.motor_controller.clear_errors_left()
                self.motor_controller.clear_errors_right()

                self.is_idle = False

            # Motor error checks (every 20 cycles)
            if self.cycle_count % 20 == 0:
                try:
                    self.logger.info("Performing periodic error check...")
                    if self.motor_controller.has_errors():
                        self.logger.info("ERRORS DETECTED in motor controller!")
                        self.motor_controller.dump_errors()
                        self.logger.info("Attempting motor reset due to errors...")
                        # First stop the motors before reset
                        self.emergency_stop("Motor controller errors detected")
                        self.reset_and_initialize_motors()
                        return
                except Exception as e:
                    self.logger.info(f'ERROR checking motor errors: {e}')
                    # First stop the motors before reset
                    self.emergency_stop("Exception during error check")
                    self.reset_and_initialize_motors()
                    return
                
            # Clip the desired velocity to the maximum speed
            velocity_target_mps = max(min(velocity_target_mps, CFG.MOTOR_CONTROL_MAX_SPEED_LINEAR_MPS), -CFG.MOTOR_CONTROL_MAX_SPEED_LINEAR_MPS)
            yaw_rate_target_rad_s = max(min(yaw_rate_target_rad_s, CFG.MOTOR_CONTROL_MAX_SPEED_ANGULAR_RADPS), -CFG.MOTOR_CONTROL_MAX_SPEED_ANGULAR_RADPS)
            
            # Calculate left and right wheel velocities
            wheel_base_width_m = CFG.ROBOT_WHEEL_DIST_M
            
            # Apply angular amplification factor to improve turning response
            angular_component = (wheel_base_width_m * yaw_rate_target_rad_s) / 2
            
            left_wheel_velocity = velocity_target_mps - angular_component
            right_wheel_velocity = velocity_target_mps + angular_component

            # Convert velocities to RPM for motor control
            left_wheel_rpm = left_wheel_velocity / RPM_TO_METERS_PER_SECOND
            right_wheel_rpm = right_wheel_velocity / RPM_TO_METERS_PER_SECOND

            # Set motor speeds
            try:
                print("Sending commands to motors...")
                self.motor_controller.set_speed_rpm_left(left_wheel_rpm)
                self.motor_controller.set_speed_rpm_right(right_wheel_rpm)
                                
            except Exception as e:
                print(f'ERROR setting motor speeds: {e}')
                print("Stopping motors and attempting reset...")
                self.emergency_stop("Exception while setting motor speeds")
                self.reset_and_initialize_motors()
                return

            self.cycle_count += 1

        except Exception as e:
            traceback.print_exc()
            self.emergency_stop("Unhandled exception in set_linear_angular_velocities")

    def emergency_stop(self, reason):
        """
        Emergency stop function to immediately halt all motor movement
        """
        print(f"EMERGENCY STOP: {reason}")
        try:
            # First try the regular stop method which sets velocities to zero
            self.stop()
        except Exception as e:
            print(f"Error during regular stop: {e}, attempting direct motor commands...")
            # If that fails, try direct commands to motors
            try:
                if hasattr(self, 'motor_controller'):
                    self.motor_controller.set_speed_rpm_left(0)
                    self.motor_controller.set_speed_rpm_right(0)
                    print("Direct zero velocity commands sent to motors")
            except Exception as ex:
                print(f"CRITICAL: Failed to emergency stop motors: {ex}")
                # Last resort - try to put motors in idle mode
                try:
                    if hasattr(self, 'motor_controller'):
                        self.motor_controller.set_idle_left()
                        self.motor_controller.set_idle_right()
                        print("Motors set to idle state")
                except:
                    print("FAILED ALL ATTEMPTS to stop motors")

    def stop(self):
        """
        Stop both motors and set them to idle state for clean shutdown.
        """
        print("Stopping and idling motors for clean shutdown...")
        try:
            # First set velocities to zero
            self.motor_controller.set_speed_rpm_left(0)
            self.motor_controller.set_speed_rpm_right(0)
            
            # Then put motors in idle state
            self.motor_controller.set_idle_left()
            self.motor_controller.set_idle_right()
            self.is_idle = True
            print("Motors successfully stopped and set to idle")
        except Exception as e:
            print(f"Error stopping motors: {e}")

    def dump_motor_config(self):
        """
        Print out current motor configuration parameters for debugging.
        """
        print("\n=== ODrive Motor Configuration ===")
        try:
            for axis in [self.motor_controller.left_axis, self.motor_controller.right_axis]:
                name = "LEFT" if axis == self.motor_controller.left_axis else "RIGHT"
                print(f"\n-- {name} MOTOR (Axis {axis}) --")
                
                # Get control mode
                mode_resp = self.motor_controller.send_command(f'r axis{axis}.controller.config.control_mode')
                try:
                    mode = int(mode_resp)
                    mode_name = "UNKNOWN"
                    if mode == 0: mode_name = "VOLTAGE"
                    elif mode == 1: mode_name = "TORQUE"
                    elif mode == 2: mode_name = "VELOCITY"
                    elif mode == 3: mode_name = "POSITION"
                    print(f"Control Mode: {mode} ({mode_name})")
                except (ValueError, TypeError):
                    print(f"Control Mode: {mode_resp}")
                
                # Get input mode
                input_mode_resp = self.motor_controller.send_command(f'r axis{axis}.controller.config.input_mode')
                try:
                    input_mode = int(input_mode_resp)
                    input_mode_name = "UNKNOWN"
                    if input_mode == 1: input_mode_name = "VEL_RAMP"
                    elif input_mode == 2: input_mode_name = "PASSTHROUGH"
                    elif input_mode == 3: input_mode_name = "MIX_CHANNELS"
                    elif input_mode == 4: input_mode_name = "TRAP_TRAJ"
                    elif input_mode == 5: input_mode_name = "TUNING"
                    print(f"Input Mode: {input_mode} ({input_mode_name})")
                except (ValueError, TypeError):
                    print(f"Input Mode: {input_mode_resp}")
                
                # Get velocity ramp rate
                ramp_rate = self.motor_controller.get_velocity_ramp(axis)
                print(f"Velocity Ramp Rate: {ramp_rate} rps/s")
                
                # Get current limits
                current_limit = self.motor_controller.send_command(f'r axis{axis}.motor.config.current_lim')
                print(f"Current Limit: {current_limit} A")
                
                # Get velocity limit
                vel_limit = self.motor_controller.send_command(f'r axis{axis}.controller.config.vel_limit')
                print(f"Velocity Limit: {vel_limit} turns/s")
                
        except Exception as e:
            print(f"Error getting motor configuration: {e}")
            traceback.print_exc()
        print("===================================\n")

def stop_motors_on_exit(signal_received, frame):
    print(">>> SIGNAL HANDLER CALLED <<<")
    print("Stopping motors before exit...")
    # Send zero velocity/torque to both motors
    try:
        # Use the clean stop method instead of calling methods directly
        motor_control.stop()
    except Exception as e:
        print(f"Error stopping motors: {e}")
    sys.exit(0)

signal.signal(signal.SIGINT, stop_motors_on_exit)  # Handle Ctrl+C
signal.signal(signal.SIGTERM, stop_motors_on_exit) # Handle kill