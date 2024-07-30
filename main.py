
import my_sx1262
# import asyncio

# asyncio.run(my_sx1262.main())
my_sx1262.pin_dio1.irq(my_sx1262.dio_echo_irq, trigger=my_sx1262.Pin.IRQ_RISING)
# my_sx1262.pin_dio1.irq(my_sx1262.dio_strobe_irq, trigger=my_sx1262.Pin.IRQ_RISING)
my_sx1262.main()