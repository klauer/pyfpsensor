# @brief Maximum size of a telegram
#
# Maximum size of a telegram including header (with length field) and data,
# in bytes.
#
MAXSIZE = 512

# @name OpCodes
#
# These constants are used to identify the protocol elements and fit to the
# opcode field of the @ref UcTelegram "telegram header".
#
SET = 0       # Set telegram
GET = 1       # Get telegram
ACK = 3       # Ack (acknowledge) telegram
TELL = 4      # Tell (event) telegram


# @name Reason codes
#
# These constants are used to notify about errors in the processing of
# @ref UcSetTelegram "Set" and @ref UcGetTelegram "Get" telegrams
# They are found in the reason field of the @ref UcAckTelegram "Ack Telegram".
REASON_OK      = 0  # All ok
REASON_ADDR    = 1  # Invalid address
REASON_RANGE   = 2  # Value out of range
REASON_IGNORED = 3  # Telegram was ignored
REASON_VERIFY  = 4  # Verify of data failed
REASON_TYPE    = 5  # Wrong type of data
REASON_UNKNW   = 99 # unknown error
