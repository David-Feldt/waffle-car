"""Main control node."""

import logging
import time

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64, Bool, String
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Path
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy

from . import constants as CFG
from .motor_control import MotorControl


class ControlNode(Node):
    """Control node class for robot drivetrain."""

    def __init__(self):
        """Initialize the ControlNode class."""
        super().__init__('control_node')
        
        # Initialize logger
        self.get_logger().info('Initializing Control Node')
        
        # Create subscribers            
        self.target_velocity_sub = self.create_subscription(
            Twist,
            'target_velocity',
            self.target_velocity_callback,
            10)
                    
        # Create publishers
        self.wheel_velocities_pub = self.create_publisher(
            Twist,  # Using Twist to publish left and right wheel velocities
            'wheel_velocities',
            10)
        
        # Set up node heartbeat
        self.node_heartbeat_pub = self.create_publisher(
            String, 
            '/node_heartbeat', 
            QoSProfile(
                depth=10,
                durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                reliability=QoSReliabilityPolicy.RELIABLE
            )
        )
        self.create_timer(0.5, self.publish_heartbeat)
        
        # Initialize controller
        self.controller = MotorControl()
        
        # Watchdog timer to detect command loss
        self.last_command_time = time.time()
        self.command_timeout = 1.0  # Stop robot if no commands for 1 second
        self.create_timer(0.2, self.watchdog_callback)  # Check for connection loss every 200ms
                
        self.get_logger().info('Control Node initialized')
        self.get_logger().info(f'Watchdog timeout set to {self.command_timeout} seconds')
    
    def publish_heartbeat(self):
        """Publish node heartbeat"""
        msg = String()
        msg.data = f"{self.get_name()}:{time.time()}"
        self.node_heartbeat_pub.publish(msg)
        
    def watchdog_callback(self):
        """Check if we've received velocity commands recently, stop robot if not"""
        time_since_last_command = time.time() - self.last_command_time
        
        if time_since_last_command > self.command_timeout:
            # No commands received for a while, stop the robot
            self.get_logger().warn(f'No velocity commands received for {time_since_last_command:.2f} seconds. Stopping robot.')
            self.controller.set_linear_angular_velocities(0.0, 0.0)
            
            # Publish zero wheel velocities for feedback
            wheel_velocities_msg = Twist()
            wheel_velocities_msg.linear.x = 0.0  # left wheel
            wheel_velocities_msg.linear.y = 0.0  # right wheel
            self.wheel_velocities_pub.publish(wheel_velocities_msg)
    
    def target_velocity_callback(self, msg):
        """Handle target velocity messages."""
        # Update the last command time
        self.last_command_time = time.time()
        
        self.controller.set_linear_angular_velocities(
            msg.linear.x, 
            msg.angular.z
        )
        # Publish wheel velocities (feedback)
        l_vel_mps = self.controller.get_left_motor_velocity()
        r_vel_mps = self.controller.get_right_motor_velocity()
        wheel_velocities_msg = Twist()
        wheel_velocities_msg.linear.x = l_vel_mps  # left wheel
        wheel_velocities_msg.linear.y = r_vel_mps  # right wheel
        self.wheel_velocities_pub.publish(wheel_velocities_msg)
        self.get_logger().info(f'Received velocity command: Linear: {msg.linear.x:.3f} m/s, Angular: {msg.angular.z:.3f} rad/s')
            
    def info(self, msg):
        """Logger compatibility method."""
        self.get_logger().info(msg)


def main(args=None):
    rclpy.init(args=args)
    
    control_node = ControlNode()
    
    try:
        rclpy.spin(control_node)
    except KeyboardInterrupt:
        control_node.get_logger().info("Control node stopped by user.")
    finally:
        # Cleanup
        control_node.controller.stop()
        control_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()