"""


Pinout of SX1262:
https://www.waveshare.com/product/raspberry-pi/boards-kits/raspberry-pi-pico-cat/pico-lora-sx1262-868m.htm

SX1262 DS:
https://files.waveshare.com/upload/e/e1/DS_SX1261-2_V1.2.pdf
   SPI on pg 50

LoRaRF github:
https://github.com/chandrawi/LoRaRF-Python/tree/main

MicroPython SPI docs:
https://docs.micropython.org/en/latest/library/machine.SPI.html#machine.SPI

Raspberry Pi doc of GPIOS:
https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html
"""

import machine
from machine import Pin, SPI, SoftSPI

pin_sck = Pin(10, Pin.OUT)
pin_mosi = Pin(11, Pin.OUT)
pin_miso = Pin(12, Pin.IN)
pin_cs = Pin(3, Pin.OUT, value=1)

pin_busy = Pin(2, Pin.IN)

# spi = SPI(0, baudrate=8000000, polarity=0, phase=0, bits=8, firstbit=SPI.MSB, sck=Pin(2), miso=Pin(4), mosi=Pin(3))

spi = SPI(1, sck=pin_sck, mosi=pin_mosi, miso=pin_miso)

def op_code(code, total_bytes):
    buff = bytearray(total_bytes)
    buff[0] = code
    buff_in = bytearray(total_bytes)
    
    pin_cs.value(0)
    spi.write_readinto(buff, buff_in)
    
    pin_cs.value(1)
    return buff_in


def get_status():
    """
    Status codes on page: 95
    """
    buff = bytearray(2)
    buff[0] = 0xc0  # getStatus
    buff_in = bytearray(2)
    
    pin_cs.value(0)
    spi.write_readinto(buff, buff_in)
    
    pin_cs.value(1)
    return (hex(buff_in[1]), hex((buff_in[1] & 0x70) >> 4), hex((buff_in[1] & 0xe) >> 1))


def set_lora():
    buff = bytearray(2)
    buff[0] = 0x8a
    buff[1] = 0x01
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def write_buffer(offset, data):
    buff = bytearray(2 + len(data))
    buff[0] = 0x0e
    buff[1] = offset
    buff[2:] = data
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def read_buffer(offset, num):
    """
    First byte is status, then data"""
    buff = bytearray(3 + num)
    buff_in = bytearray(3 + num)
    buff[0] = 0x1e
    buff[1] = offset
    pin_cs.value(0)
    spi.write_readinto(buff, buff_in)
    pin_cs.value(1)
    return buff_in[3:]  # throwing away status

def set_buffer_base_addr():
    """
    pg. 93
    """
    buff = bytearray(3)
    buff[0] = 0x8f
    buff[0] = 0  # tx 
    buff[0] = 0  # rx
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_pa_config():
    """
    pg. 76
    Think I have the SX1262
    """
    buff = bytearray(5)
    buff[0] = 0x95
    # max power?  +22 dBm
    buff[1] = 0x04
    buff[2] = 0x07
    buff[3] = 0x0
    buff[4] = 0x1
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_tx_params():
    """
    pg. 84
    """
    buff = bytearray(3)
    buff[0] = 0x8e
    buff[1] = 0x16  # 22 dBm
    buff[2] = 0x06 # 1700 us
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)



def set_packet_params(payload_size):
    """
    pg. 88
    params 1 through 9

    pg 91 describes packet parameters
    1 and 2: preamble length
    3: 0x0 for variable length header
    4: size of payload
    5: 0x1 crc on
    6: 0x0 standard iq
    
    pg 87 describes parameters (modulation parameters? not packet?)
    """
    buff = bytearray(10)
    buff[0] = 0x8c
    buff[2] = 0xe  # no idea...
    buff[3] = 0x0
    buff[4] = payload_size
    buff[5] = 0x1
    buff[6] = 0x0
    
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_modulation_params():
    """
    pg. 87
    """
    buff = bytearray(10)
    buff[0] = 0x8b
    buff[1] = 0 # SF
    # buff[2] = 0x0  # BW 7.81 kHz  (lowest)
    buff[3] = 0x01  # CR
    # buff[4] = 0 # low data rate optimize if  0x01
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_tx(timeout=0):
    """
    timeout = 15.625 us * timeout
    pg 68
    """
    buff = bytearray(4)
    buff[0] = 0x83
    # Timeout not implemented
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_standby(mode):
    """
    0: STDBY_RC
    1: STBY_XOSC
    pg. 68
    """
    buff = bytearray(2)
    buff[0] = 0x80
    buff[1] = mode
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def get_errors():
    """
    pg. 98
    Status codes on page: 95
    """
    buff = bytearray(4)
    buff[0] = 0x17
    buff_in = bytearray(4)
    pin_cs.value(0)
    spi.write_readinto(buff, buff_in)
    pin_cs.value(1)
    
    return buff_in[1:]


def clear_errors():
    """
    pg. 98
    """
    buff = bytearray(3)
    buff[0] = 0x07
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_reg_mode(mode):
    """
    pg. 74

    0: LDO only
    1: DC + DC and LDO
    """
    buff = bytearray(2)
    buff[0] = 0x96
    buff[1] = mode
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_rf_freq(freq):
    """
    try 902300000
    """
    rfFreq = int(freq * 33554432 / 32000000)
    # buf = (
    #         (rfFreq >> 24) & 0xFF,
    #         (rfFreq >> 16) & 0xFF,
    #         (rfFreq >> 8) & 0xFF,
    #         rfFreq & 0xFF
    #     )
    #     self._writeBytes(0x86, buf, 4)
    buf = bytearray(5)
    buf[0] = 0x86
    buf[1] = (rfFreq >> 24) & 0xff
    buf[2] = (rfFreq >> 16) & 0xff
    buf[3] = (rfFreq >> 8) & 0xff
    buf[4] = rfFreq & 0xff
    pin_cs.value(0)
    spi.write(buf)
    pin_cs.value(1)




# Basic transmit description page 99
# 2. set_lora
set_lora()
# 3. set_rf_freq
set_rf_freq(902300000)

# 4. PA config
set_pa_config()

# 5. set_tx_power
set_tx_params()

# 6. set_buffer_base_addr
set_buffer_base_addr()

# 7. write buffer
write_buffer(0, b'hi there')

# 8. set modulation params
set_modulation_params()

# 9. set packet params
set_packet_params(8)

# 10. config DIO and IRQ
# 11. sync word
# 12. transmit
set_tx()

# Lora model description pg. 37


