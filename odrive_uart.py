import time

import odrive.enums
import serial
print(serial.__file__)
print(serial.__version__)
# from RPi import GPIO  # Import GPIO module

import constants as CFG

# GPIO setup for resetting ODrive
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(5, GPIO.OUT)
    
class ODriveUART:
    """
    A class to interface with ODrive motor controllers over UART.
    """

    AXIS_STATE_CLOSED_LOOP_CONTROL = 8
    ERROR_DICT = {k: v for k, v in odrive.enums.__dict__.items() if k.startswith("AXIS_ERROR_")}

    def __init__(self, port='/dev/ttyACM0', left_axis=1, right_axis=0, dir_left=1, dir_right=1):
        """
        Initialize the ODriveUART class with the specified parameters.
        """
        self.bus = serial.Serial(
            port=port,
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        self.left_axis = left_axis
        self.right_axis = right_axis
        self.dir_left = dir_left
        self.dir_right = dir_right

        # Clear the ASCII UART buffer
        self.bus.reset_input_buffer()
        self.bus.reset_output_buffer()

    def send_command(self, command: str):
        """
        Send a command to the ODrive and return the response if applicable.
        """
        self.bus.reset_input_buffer()
        self.bus.write(f"{command}\n".encode())
        if command.startswith('r') or command.startswith('f'):
            response = self.bus.readline().decode('ascii').strip()
            if response == '':
                print(f"No response received for command: {command}")
            return response
    
    def get_errors_left(self):
        """
        Get errors for the left axis.
        """
        return self.get_errors(self.left_axis)

    def get_errors_right(self):
        """
        Get errors for the right axis.
        """
        return self.get_errors(self.right_axis)

    def get_errors(self, axis):
        """
        Get errors for the specified axis.
        """
        error_code = -1
        error_name = 'Unknown error'
        error_response = self.send_command(f'r axis{axis}.error')
        try:
            cleaned_response = ''.join(c for c in error_response if c.isdigit())
            error_code = int(cleaned_response)
            error_name = self.ERROR_DICT.get(error_code, error_name)
        except ValueError:
            print(f"Unexpected error response format: {error_response}")
        return error_code, error_name

    def has_errors(self):
        """
        Check if there are any errors on either axis.
        """
        for axis in [0,1]:
            error_response = self.send_command(f'r axis{axis}.error')
            try:
                cleaned_response = ''.join(c for c in error_response if c.isdigit())
                error_code = int(cleaned_response)
            except ValueError:
                print(f"Unexpected error response format: {error_response}")
                return True
            if error_code != 0:
                return True
        return False

    def dump_errors(self):
        """
        Print all errors for both axes and their components.
        """
        error_sources = [
            "axis0","axis0.encoder", "axis0.controller", "axis0.motor",
            "axis1","axis1.encoder", "axis1.controller", "axis1.motor"
        ]
        print('======= ODrive Errors =======')
        for src in error_sources:
            error_response = self.send_command(f'r {src}.error')
            try:
                cleaned_response = ''.join(c for c in error_response if c.isdigit())
                error_code = int(cleaned_response)
            except ValueError:
                print(f"Unexpected error response format: {error_response}")
                continue

            if error_code == 0:
                print(src+'.error=0x0: \033[92mNone\033[0m')
                continue

            error_prefix = f"{src.split('.')[-1].strip('01').upper()}_ERROR"
            error_dict = {name: value for name, value in vars(odrive.enums).items() if name.startswith(error_prefix)}
            error_string = ""
            for error_name, code in error_dict.items():
                if error_code & code:
                    error_string += f"{error_name.replace(error_prefix + '_', '').lower().replace('_', ' ')}, "
            error_string = error_string.rstrip(", ")
            print(f"{src}.error={hex(error_code)}: \033[91m{error_string}\033[0m")
        print('=============================')

    def enable_torque_mode_left(self):
        """
        Enable torque control mode for the left axis.
        """
        self.enable_torque_mode(self.left_axis)

    def enable_torque_mode_right(self):
        """
        Enable torque control mode for the right axis.
        """
        self.enable_torque_mode(self.right_axis)

    def enable_torque_mode(self, axis):
        """
        Enable torque control mode for the specified axis.
        """
        self.send_command(f'w axis{axis}.controller.config.control_mode 1')
        self.send_command(f'w axis{axis}.controller.config.input_mode 1')
        print(f"Axis {axis} set to torque control mode")

    def enable_velocity_mode_left(self):
        """
        Enable velocity control mode for the left axis.
        """
        self.enable_velocity_mode(self.left_axis)

    def enable_velocity_mode_right(self):
        """
        Enable velocity control mode for the right axis.
        """
        self.enable_velocity_mode(self.right_axis)

    def enable_velocity_mode(self, axis):
        """
        Enable velocity control mode for the specified axis.
        """
        self.send_command(f'w axis{axis}.controller.config.control_mode 2')
        self.send_command(f'w axis{axis}.controller.config.input_mode 2')
        self.send_command(f'w axis{axis}.controller.config.vel_ramp_rate 100')  # adjust to desired accel
        self.send_command(f'w axis{axis}.controller.config.vel_limit 20')       # optional: raise speed limit

        print(f"Axis {axis} set to velocity control mode")

    def start_left(self):
        """
        Start the left axis.
        """
        self.start(self.left_axis)

    def start_right(self):
        """
        Start the right axis.
        """
        self.start(self.right_axis)

    def start(self, axis):
        """
        Start the specified axis.
        """
        self.send_command(f'w axis{axis}.requested_state 8')

    def set_speed_rpm_left(self, rpm):
        """
        Set the speed in RPM for the left axis.
        """
        self.set_speed_rpm(self.left_axis, rpm, self.dir_left)

    def set_speed_rpm_right(self, rpm):
        """
        Set the speed in RPM for the right axis.
        """
        self.set_speed_rpm(self.right_axis, rpm, self.dir_right)

    def set_speed_rpm(self, axis, rpm, direction):
        """
        Set the speed in RPM for the specified axis.
        """
        rps = rpm / 60
        self.send_command(f'w axis{axis}.controller.input_vel {rps * direction:.4f}')

    def set_speed_mps_left(self, mps):
        rps = mps / (CFG.ROBOT_WHEEL_RADIUS_M * 2 * 3.14159)
        self.send_command(f'w axis{self.left_axis}.controller.input_vel {rps * self.dir_left:.4f}')

    def set_speed_mps_right(self, mps):
        rps = mps / (CFG.ROBOT_WHEEL_RADIUS_M * 2 * 3.14159)
        self.send_command(f'w axis{self.right_axis}.controller.input_vel {rps * self.dir_right:.4f}')

    def set_torque_nm_left(self, nm):
        """
        Set the torque in Nm for the left axis.
        """
        self.set_torque_nm(self.left_axis, nm, self.dir_left)

    def set_torque_nm_right(self, nm):
        """
        Set the torque in Nm for the right axis.
        """
        self.set_torque_nm(self.right_axis, nm, self.dir_right)

    def set_torque_nm(self, axis, nm, direction):
        """
        Set the torque in Nm for the specified axis.
        """
        torque_bias = 0.05 # Small torque bias in Nm
        adjusted_torque = nm * direction + (torque_bias * direction * (1 if nm >= 0 else -1))
        self.send_command(f'c {axis} {adjusted_torque:.4f}')
        self.send_command(f'u {axis}')

    def get_speed_rpm_left(self):
        """
        Get the speed in RPM for the left axis.
        """
        return self.get_speed_rpm(self.left_axis, self.dir_left)

    def get_speed_rpm_right(self):
        """
        Get the speed in RPM for the right axis.
        """
        return self.get_speed_rpm(self.right_axis, self.dir_right)

    def get_speed_rpm(self, axis, direction):
        """
        Get the speed in RPM for the specified axis.
        """
        response = self.send_command(f'r axis{axis}.encoder.vel_estimate')
        return float(response) * direction * 60

    def get_position_turns_left(self):
        """
        Get the position in turns for the left axis.
        """
        return self.get_position_turns(self.left_axis, self.dir_left)

    def get_position_turns_right(self):
        """
        Get the position in turns for the right axis.
        """
        return self.get_position_turns(self.right_axis, self.dir_right)

    def get_position_turns(self, axis, direction):
        """
        Get the position in turns for the specified axis.
        """
        response = self.send_command(f'r axis{axis}.encoder.pos_estimate')
        return float(response) * direction
    
    def get_pos_vel_left(self):
        """
        Get the position and velocity for the left axis.
        """
        return self.get_pos_vel(self.left_axis, self.dir_left)

    def get_pos_vel_right(self):
        """
        Get the position and velocity for the right axis.
        """
        return self.get_pos_vel(self.right_axis, self.dir_right)

    def get_pos_vel(self, axis, direction):
        """
        Get the position and velocity for the specified axis.
        """
        pos, vel = self.send_command(f'f {axis}').split(' ')
        return float(pos) * direction, float(vel) * direction * 60

    def stop_left(self):
        """
        Stop the left axis.
        """
        self.stop(self.left_axis)

    def stop_right(self):
        """
        Stop the right axis.
        """
        self.stop(self.right_axis)

    def stop(self, axis):
        """
        Stop the specified axis.
        """
        self.send_command(f'w axis{axis}.controller.input_vel 0')
        self.send_command(f'w axis{axis}.controller.input_torque 0')

    def set_idle_left(self):
        """
        Set the left axis to idle mode.
        """
        self.set_idle(self.left_axis)

    def set_idle_right(self):
        """
        Set the right axis to idle mode.
        """
        self.set_idle(self.right_axis)

    def set_idle(self, axis):
        """
        Set the specified axis to idle mode (requested_state = 1).
        This fully disables the motor controller rather than just setting zero velocity.
        """
        self.send_command(f'w axis{axis}.requested_state 1')
        print(f"Axis {axis} set to idle state")

    def check_errors_left(self):
        """
        Check for errors on the left axis.
        """
        return self.check_errors(self.left_axis)

    def check_errors_right(self):
        """
        Check for errors on the right axis.
        """
        return self.check_errors(self.right_axis)

    def check_errors(self, axis):
        """
        Check for errors on the specified axis.
        """
        response = self.send_command(f'r axis{axis}.error')
        try:
            cleaned_response = ''.join(c for c in response if c.isdigit())
            return int(cleaned_response) != 0
        except ValueError:
            print(f"Unexpected response format: {response}")
            return True

    def clear_errors_left(self):
        """
        Clear errors on the left axis.
        """
        self.clear_errors(self.left_axis)

    def clear_errors_right(self):
        """
        Clear errors on the right axis.
        """
        self.clear_errors(self.right_axis)

    def clear_errors(self, axis):
        """
        Clear errors on the specified axis.
        """
        self.send_command(f'w axis{axis}.error 0')
        self.send_command(f'w axis{axis}.requested_state {self.AXIS_STATE_CLOSED_LOOP_CONTROL}')

    def enable_watchdog_left(self):
        """
        Enable the watchdog for the left axis.
        """
        self.enable_watchdog(self.left_axis)

    def enable_watchdog_right(self):
        """
        Enable the watchdog for the right axis.
        """
        self.enable_watchdog(self.right_axis)

    def enable_watchdog(self, axis):
        """
        Enable the watchdog for the specified axis.
        """
        self.send_command(f'w axis{axis}.config.enable_watchdog 1')

    def disable_watchdog_left(self):
        """
        Disable the watchdog for the left axis.
        """
        self.disable_watchdog(self.left_axis)

    def disable_watchdog_right(self):
        """
        Disable the watchdog for the right axis.
        """
        self.disable_watchdog(self.right_axis)

    def disable_watchdog(self, axis):
        """
        Disable the watchdog for the specified axis.
        """
        self.send_command(f'w axis{axis}.config.enable_watchdog 0')

    def config_velocity_ramp_left(self, ramp_rate=10.0):
        """
        Set the velocity ramp rate for the left axis.
        """
        self.config_velocity_ramp(self.left_axis, ramp_rate)
    
    def config_velocity_ramp_right(self, ramp_rate=10.0):
        """
        Set the velocity ramp rate for the right axis.
        """
        self.config_velocity_ramp(self.right_axis, ramp_rate)
    
    def config_velocity_ramp(self, axis, ramp_rate=10.0):
        """
        Set the velocity ramp rate for the specified axis.
        Higher values = faster acceleration/deceleration.
        Default ODrive value is often 1.0 rps/s which is very slow.
        
        :param axis: Motor axis (0 or 1)
        :param ramp_rate: Ramp rate in rotations per second per second (rps/s)
        """
        # Set the velocity ramp rate (rps/s)
        self.send_command(f'w axis{axis}.controller.config.vel_ramp_rate {ramp_rate:.3f}')
        print(f"Axis {axis} velocity ramp rate set to {ramp_rate:.3f} rps/s")
    
    def disable_velocity_ramping_left(self):
        """
        Disable velocity ramping for the left axis for immediate acceleration.
        """
        self.disable_velocity_ramping(self.left_axis)
    
    def disable_velocity_ramping_right(self):
        """
        Disable velocity ramping for the right axis for immediate acceleration.
        """
        self.disable_velocity_ramping(self.right_axis)
    
    def disable_velocity_ramping(self, axis):
        """
        Disable velocity ramping for immediate acceleration.
        This sets input_mode to 2 (PASSTHROUGH) instead of 1 (VEL_RAMP).
        
        :param axis: Motor axis (0 or 1)
        """
        self.send_command(f'w axis{axis}.controller.config.input_mode 2')
        print(f"Axis {axis} velocity ramping disabled, using PASSTHROUGH mode")
    
    def set_current_limit(self, axis, current_limit=40.0):
        """
        Set the current limit for the motor.
        Higher current = more torque = faster acceleration.
        
        :param axis: Motor axis (0 or 1)
        :param current_limit: Current limit in Amps
        """
        self.send_command(f'w axis{axis}.motor.config.current_lim {current_limit:.1f}')
        print(f"Axis {axis} current limit set to {current_limit:.1f} A")
    
    def get_velocity_ramp(self, axis):
        """
        Get the current velocity ramp rate for the specified axis.
        """
        response = self.send_command(f'r axis{axis}.controller.config.vel_ramp_rate')
        try:
            return float(response)
        except (ValueError, TypeError):
            print(f"Unexpected response: {response}")
            return None

    def reboot(self):
        """
        Save configuration and reboot the ODrive.
        """
        print("Saving configuration and rebooting ODrive...")
        return self.send_command('sr')

def reset_odrive(odrive_instance=None):
    """Reboot the ODrive using serial command 'sr' via ODriveUART."""
    # try:
    #     if odrive_instance:
    #         odrive_instance.reboot()
    #         print("ODrive rebooted using provided instance (serial)")
    #         return True
    #     else:
    #         # If no instance is provided, create a temporary one using the default port from config
    #         from lib.constants import MOTOR_CONTROL_SERIAL_PORT, MOTOR_CONTROL_LEFT_MOTOR_AXIS, MOTOR_CONTROL_RIGHT_MOTOR_AXIS, MOTOR_CONTROL_LEFT_MOTOR_DIR, MOTOR_CONTROL_RIGHT_MOTOR_DIR
    #         uart = ODriveUART(
    #             port=MOTOR_CONTROL_SERIAL_PORT,
    #             left_axis=MOTOR_CONTROL_LEFT_MOTOR_AXIS,
    #             right_axis=MOTOR_CONTROL_RIGHT_MOTOR_AXIS,
    #             dir_left=MOTOR_CONTROL_LEFT_MOTOR_DIR,
    #             dir_right=MOTOR_CONTROL_RIGHT_MOTOR_DIR
    #         )
    #         uart.reboot()
    #         print("ODrive rebooted using serial command on default port")
    #         uart.bus.close()
    #         return True
    # except Exception as e:
    #     print(f"ODrive reboot failed (serial): {e}")
    #     return False

if __name__ == '__main__':
    # Initialize with directions for left and right motors
    motor_controller = ODriveUART('/dev/odrive', left_axis=0, right_axis=1, dir_left=1, dir_right=-1)

    # Start the motors and set to velocity mode
    motor_controller.start_left()
    motor_controller.start_right()
    
    # Configure for velocity mode with PASSTHROUGH (direct drive) for immediate response
    motor_controller.enable_velocity_mode_left()
    motor_controller.enable_velocity_mode_right()
    
    # Disable velocity ramping for direct drive (immediate velocity changes)
    print("Enabling direct drive (PASSTHROUGH mode)...")
    motor_controller.disable_velocity_ramping_left()
    motor_controller.disable_velocity_ramping_right()
    
    # Check current ramp settings (should show that input_mode is now 2 for PASSTHROUGH)
    left_ramp = motor_controller.get_velocity_ramp(motor_controller.left_axis)
    right_ramp = motor_controller.get_velocity_ramp(motor_controller.right_axis)
    print(f"Configured ramp rates - Left: {left_ramp} rps/s, Right: {right_ramp} rps/s")
    print("Note: Ramp rates don't apply in PASSTHROUGH mode")

    try:
        # Test direct velocity control (should respond immediately)
        print("Testing direct velocity control...")
        for speed in [0.5, 1.0, 2.0, 0.0, -1.0, 0.0]:
            print(f"Setting speed to {speed} RPS...")
            motor_controller.set_speed_rpm_left(speed * 60)  # Convert RPS to RPM
            motor_controller.set_speed_rpm_right(speed * 60)
            time.sleep(2)

    except Exception as e:
        print(e)
    finally:
        print("Shutting down motors...")
        motor_controller.stop_left()
        motor_controller.stop_right()
        motor_controller.set_idle_left()
        motor_controller.set_idle_right()