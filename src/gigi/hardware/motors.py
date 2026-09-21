"""
Hardware driver for PCA9685 16-channel PWM servo controller over I2C.
Supports Orange Pi 5 Pro and provides simulation fallback for host development.
"""

import math
import time
import logging
from typing import Optional

from gigi.core.config import (
    IS_ROBOT,
    SMBUS_INTERFACE,
    PCA9685_ADDRESS,
    PWM_FREQUENCY,
)

logger = logging.getLogger(__name__)

# PCA9685 Registers
MODE1 = 0x00
MODE2 = 0x01
SUBADR1 = 0x02
SUBADR2 = 0x03
SUBADR3 = 0x04
PRESCALE = 0xFE
LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09
ALL_LED_ON_L = 0xFA
ALL_LED_ON_H = 0xFB
ALL_LED_OFF_L = 0xFC
ALL_LED_OFF_H = 0xFD

# Control Bits
RESTART = 0x80
SLEEP = 0x10
ALLCALL = 0x01
INVRT = 0x10
OUTDRV = 0x04


class PCA9685Controller:
    """
    Direct I2C interface to PCA9685 PWM controller.
    Controls servo motors for neck, torso, shoulders, and elbows.
    """

    def __init__(
        self,
        interface: int = SMBUS_INTERFACE,
        address: int = PCA9685_ADDRESS,
        freq_hz: int = PWM_FREQUENCY,
    ):
        self.interface = interface
        self.address = address
        self.freq_hz = freq_hz
        self.bus = None
        self.is_hardware_available = False

        if IS_ROBOT:
            try:
                from smbus2 import SMBus

                self.bus = SMBus(self.interface)
                self._init_hardware()
                self.is_hardware_available = True
                logger.info(
                    f"PCA9685 initialized on I2C bus {self.interface}, addr 0x{self.address:02X} @ {self.freq_hz}Hz"
                )
            except Exception as e:
                logger.warning(
                    f"Could not open I2C bus {self.interface} at 0x{self.address:02X}: {e}. Running in simulation mode."
                )
        else:
            logger.info("Running PCA9685 in software simulation mode (non-robot environment).")

    def _init_hardware(self) -> None:
        """Configures PCA9685 control registers."""
        self.bus.write_byte_data(self.address, MODE2, OUTDRV)
        self.bus.write_byte_data(self.address, MODE1, ALLCALL)
        time.sleep(0.005)

        mode1 = self.bus.read_byte_data(self.address, MODE1)
        mode1 = mode1 & ~SLEEP
        self.bus.write_byte_data(self.address, MODE1, mode1)
        time.sleep(0.005)

        # Set PWM frequency
        prescaleval = 25000000.0 / (4096.0 * float(self.freq_hz)) - 1.0
        prescale = int(math.floor(prescaleval + 0.5))

        oldmode = self.bus.read_byte_data(self.address, MODE1)
        newmode = (oldmode & 0x7F) | 0x10
        self.bus.write_byte_data(self.address, MODE1, newmode)
        self.bus.write_byte_data(self.address, PRESCALE, prescale)
        self.bus.write_byte_data(self.address, MODE1, oldmode)
        time.sleep(0.005)
        self.bus.write_byte_data(self.address, MODE1, oldmode | 0x80)

    def set_pwm(self, channel: int, on: int, off: int) -> None:
        """Sets PWM ON and OFF counts (0 to 4095) for a given channel."""
        if not self.is_hardware_available or self.bus is None:
            return

        try:
            self.bus.write_byte_data(self.address, LED0_ON_L + 4 * channel, on & 0xFF)
            self.bus.write_byte_data(self.address, LED0_ON_H + 4 * channel, (on >> 8) & 0xFF)
            self.bus.write_byte_data(self.address, LED0_OFF_L + 4 * channel, off & 0xFF)
            self.bus.write_byte_data(self.address, LED0_OFF_H + 4 * channel, (off >> 8) & 0xFF)
        except Exception as e:
            logger.error(f"Error setting PWM for channel {channel}: {e}")

    def set_all_pwm(self, on: int, off: int) -> None:
        """Sets PWM ON and OFF counts for all 16 channels simultaneously."""
        if not self.is_hardware_available or self.bus is None:
            return

        try:
            self.bus.write_byte_data(self.address, ALL_LED_ON_L, on & 0xFF)
            self.bus.write_byte_data(self.address, ALL_LED_ON_H, (on >> 8) & 0xFF)
            self.bus.write_byte_data(self.address, ALL_LED_OFF_L, off & 0xFF)
            self.bus.write_byte_data(self.address, ALL_LED_OFF_H, (off >> 8) & 0xFF)
        except Exception as e:
            logger.error(f"Error setting all PWM: {e}")

    def reset_motor(self, channel: int) -> None:
        """Disables output on a single channel."""
        self.set_pwm(channel, 0, 4096)

    def reset_all_motors(self) -> None:
        """Disables output on all channels."""
        self.set_all_pwm(0, 4096)

    def software_reset(self) -> None:
        """Issues I2C General Call Software Reset."""
        if self.is_hardware_available and self.bus is not None:
            try:
                self.bus.write_byte_data(self.address, 0x06, 0x00)
            except Exception as e:
                logger.error(f"Error issuing software reset: {e}")

    def close(self) -> None:
        """Releases the I2C bus."""
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None

    def __del__(self):
        self.close()


# Alias for backwards compatibility
Motors = PCA9685Controller
