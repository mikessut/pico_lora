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
from machine import Pin, SPI, Timer
import time
import asyncio

pin_sck = Pin(10, Pin.OUT)
pin_mosi = Pin(11, Pin.OUT)
pin_miso = Pin(12, Pin.IN)
pin_cs = Pin(3, Pin.OUT, value=1)

pin_busy = Pin(2, Pin.IN)

pin_reset = Pin(15, Pin.OUT, value=1)

pin_dio1 = Pin(20, Pin.IN)

pin_led = Pin('LED', Pin.OUT)


spi = SPI(1, sck=pin_sck, mosi=pin_mosi, miso=pin_miso)

def op_code(code, total_bytes):
    buff = bytearray(total_bytes)
    buff[0] = code
    buff_in = bytearray(total_bytes)
    
    pin_cs.value(0)
    spi.write_readinto(buff, buff_in)
    
    pin_cs.value(1)
    return buff_in


status_modes = {
    0x2: 'Standby_RC',
    0x3: 'STBY_XOSC',
    0x4: 'FS',
    0x5: 'RX',
    0x6: 'TX',
}

cmd_status = {
    0x2: 'data avail',
    0x3: 'command timeout',
    0x4: 'command proc error',
    0x5: 'failure to execute command',
    0x6: 'command tx done (xmision terminated)',
}

def get_status():
    """
    Status codes on page: 95

    chip modes [6:4]:
    0x2: Standby_RC
    0x3: STBY_XOSC
    0x4: FS
    0x5: RX
    0x6: TX

    3:1 command status:
    0x2: data avail
    0x3: command timeout
    0x4: command proc error
    0x5: failure to execute command
    0x6: command tx done (xmision terminated)
    """
    buff = bytearray(2)
    buff[0] = 0xc0  # getStatus
    buff_in = bytearray(2)
    
    pin_cs.value(0)
    spi.write_readinto(buff, buff_in)
    
    pin_cs.value(1)
    return (buff_in[1], ((buff_in[1] & 0x70) >> 4), ((buff_in[1] & 0xe) >> 1),
            status_modes.get((buff_in[1] & 0x70) >> 4),
            cmd_status.get((buff_in[1] & 0xe) >> 1)
            )


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
    # buff[1] = 
    buff[2] = 0xe  # no idea... preamble length
    buff[3] = 0x0  # 0 => variable length packet
    buff[4] = payload_size  # in receive mode it is the max we can receive
    buff[5] = 0x1  # crc on
    buff[6] = 0x0  # Standard Iq
    
    pin_cs.value(0)
    spi.write(buff)
    pin_cs.value(1)


def set_modulation_params():
    """
    pg. 87
    """
    buff = bytearray(9)
    buff[0] = 0x8b
    # buff[1] = 0x1 # SF5  pg 87
    buff[1] = 0x0c # SF7  pg 87 longest time on error
    # buff[2] = 0x0  # BW 7.81 kHz  (lowest)
    buff[3] = 0x04  # CR 1-4 higher has more error immunity
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


def set_rx(timeout=0):
    """
    pg. 69
    0xFFFFFF for continuous mode
    """
    buf = bytearray(4)
    buf[0] = 0x82
    buf[1] = (timeout >> 16) & 0xff
    buf[2] = (timeout >> 8) & 0xff
    buf[3] = timeout & 0xff
    pin_cs.value(0)
    spi.write(buf)
    pin_cs.value(1)


def get_irq_status():
    """
    pg. 80
    """
    buf = bytearray(4)
    buf_in = bytearray(4)
    buf[0] = 0x12
    
    pin_cs.value(0)
    spi.write_readinto(buf, buf_in)
    pin_cs.value(1)
    return buf_in[1:]


def clear_irq_status(mask):
    """
    pg. 81
    """
    buf = bytearray(3)
    buf[0] = 0x02
    buf[1] = (mask >> 8) & 0xff
    buf[2] = mask & 0xff
    pin_cs.value(0)
    spi.write(buf)
    pin_cs.value(1)


def read_reg(reg):
    """
    IRQ_reg: pg. 80"""
    pass


def set_dio_irq_params(mask):
    """
    pg 79
    """
    buf = bytearray(9)
    buf[0] = 0x08
    buf[1] = (mask >> 8) & 0xff
    buf[2] = mask & 0xff
    # set irq to DIO1
    buf[3] = (mask >> 8) & 0xff
    buf[4] = mask & 0xff
    
    pin_cs.value(0)
    spi.write(buf)
    pin_cs.value(1)


def SetDIO2AsRfSwitchCtrl():
    buf = bytearray(2)
    buf[0] = 0x9d
    buf[1] = 0x1  # DIO2 as RF switch
    pin_cs.value(0)
    spi.write(buf)
    pin_cs.value(1)


def SetDIO3AsTCXOCtrl(delay=5 << 6):
    """
    pg 81
    """
    buf = bytearray(5)
    buf[0] = 0x97
    # buf[1] = 0x07  # 3.3 V? not sur what this should be
    buf[1] = 0x01  # 1.7 V? not sur what this should be
    buf[2] = (delay >> 16) & 0xff
    buf[3] = (delay >> 8) & 0xff 
    buf[4] = delay & 0xff
    pin_cs.value(0)
    spi.write(buf)
    pin_cs.value(1)


def GetRxBufferStatus():
    """
    pg 96
    returns 3 bytes: Status, PayloadLengthRx, RxStartBufferPointer
    """
    buf = bytearray(4)
    buf[0] = 0x13
    buf_in = bytearray(4)
    pin_cs.value(0)
    spi.write_readinto(buf, buf_in)
    pin_cs.value(1)
    return buf_in[1:]


def tx(payload: bytes):
    # Basic transmit description page 99
    # 2. set_lora
    SetDIO2AsRfSwitchCtrl()
    SetDIO3AsTCXOCtrl()
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
    write_buffer(0, payload)

    # 8. set modulation params
    set_modulation_params()

    # 9. set packet params
    set_packet_params(len(payload))

    # 10. config DIO and IRQ:  TxDone IRQ and map this IRQ to a DIO (DIO1, DIO2 or DIO3)
    set_dio_irq_params(0x1)
    # 11. sync word
    # 12. transmit
    set_tx()


def rx():
    # 1. set stby
    # 2. set lora
    clear_errors()
    SetDIO2AsRfSwitchCtrl()
    SetDIO3AsTCXOCtrl()
    set_lora()
    # 3. set frequency
    set_rf_freq(902300000)
    # 4. set base addr
    set_buffer_base_addr()
    # 5. modulation params
    set_modulation_params()
    # 6. frame format
    set_packet_params(50)  # max rx length
    # 7. IRQs: to select the IRQ RxDone and map this IRQ to a DIO (DIO1 or DIO2 or DIO3), set IRQ Timeout as well
    set_dio_irq_params(0x202)

    # 8. sync word
    # 9. setrx
    set_rx()


def led_blink(num, delay=0.25):
    for _ in range(num):
        pin_led.value(1)
        time.sleep(delay)
        pin_led.value(0)
        time.sleep(delay)
    

def status_blink():
    _, mode, cmd, _, _ = get_status()
    led_blink(mode, .25)


def main():
    
    # await asyncio.sleep_ms(2000)
    time.sleep(2)
    clear_errors()
    clear_irq_status(1)
    
    # led_blink(5)
    status_blink()
    
    tim = Timer(-1)
    tim.init(mode=Timer.PERIODIC, period=5000, callback=lambda x:status_blink())
    
    # tx(b'strobe')
    rx()
        

payload = b'empty'

def dio_echo_irq(pin):
    

    tmp = get_irq_status()
    print(tmp)

    if tmp[2] & 0x2 == 0x2:
        # rxdone
        led_blink(1)
        
        buf = GetRxBufferStatus() # Status, PayloadLengthRx, RxStartBufferPointer
        payload = read_buffer(buf[2], buf[1])
        set_standby(0)
        tx(payload)

    elif tmp[2] & 0x1 == 0x1:
        # txdone
        led_blink(2)
    
        # tx()
        # back to rx
        set_standby(0)
        rx()
    
    clear_irq_status(0x3)


def dio_rx_irq(pin):
    
    tmp = get_irq_status()
    print(tmp)

    if tmp[2] & 0x2 == 0x2:
        # rxdone
        led_blink(1)
        
        buf = GetRxBufferStatus() # Status, PayloadLengthRx, RxStartBufferPointer
        payload = read_buffer(buf[2], buf[1])
        print("rcvd", payload)
        set_standby(0)
        # tx(payload)
        # pass
    elif tmp[2] & 0x1 == 0x1:
        # txdone
        led_blink(2) 
    
        # tx()
        # back to rx
        set_standby(0)
        rx()
    
    clear_irq_status(0x3)
    


def dio_strobe_irq(pin):
    

    tmp = get_irq_status()
    print(tmp)

    if tmp[2] & 0x2 == 0x2:
        # rxdone
        led_blink(1)
        
        # buf = GetRxBufferStatus() # Status, PayloadLengthRx, RxStartBufferPointer
        # payload = read_buffer(buf[2], buf[1])
        # set_standby(0)
        # tx(payload)
        pass
    elif tmp[2] & 0x1 == 0x1:
        # txdone
        led_blink(2)

        tx(b'strobe')
        # back to rx
        
    
    clear_irq_status(0x3)

# pin_dio1.irq(dio_echo_irq, trigger=Pin.IRQ_RISING)
pin_dio1.irq(dio_rx_irq, trigger=Pin.IRQ_RISING)


# Lora model description pg. 37


