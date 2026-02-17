# FBB Forwarding Protocol

**Jean-Paul Roubelat, F6FBB**

1986

> *This markdown document was compiled from publicly available FBB protocol documentation. Primary sources include [f6fbb.org](https://www.f6fbb.org/protocole.html), [packet-radio.net](https://packet-radio.net/fbb-forward-protocol/), and the [Winlink B2F specification](https://winlink.org/B2F). It has not been verified manually for correctness. Please raise an issue in this repo with any corrections.*

## Abstract

The FBB (F6FBB) Forwarding Protocol is a message forwarding protocol for amateur packet radio bulletin board systems (BBS). Originally developed in 1986 by Jean-Paul Roubelat (F6FBB), the protocol provides efficient bidirectional message transfer between BBS nodes over AX.25 packet radio networks, PACTOR on HF, and Internet connections.

The protocol is designed to minimize command overhead on long-distance links by batching multiple message proposals and reversing transfer direction after each data block. FBB forwarding has become a de facto standard in the amateur radio BBS community and forms the basis for extended protocols such as the Winlink B2F protocol.

## 1. Introduction

Standard amateur radio BBS forwarding protocols were designed for simple keyboard-to-keyboard operation. The FBB protocol improves upon earlier protocols (such as MBL/RLI) by:

- Sending multiple message proposals in a single block
- Minimizing round-trip delays on long links through Nodes and digipeaters
- Supporting compressed message transfer
- Using unique Message IDs (MIDs) and Bulletin IDs (BIDs) to prevent duplicate messages

The protocol operates in three modes:

1. **ASCII Mode** - Basic uncompressed text transfer
2. **Compressed Mode (B/B1)** - LZHUF-compressed transfer
3. **Extended Mode (B2)** - Encapsulated messages with attachments (Winlink B2F)

## 2. System Identifier (SID)

### 2.1 SID Format

The System Identifier (SID) is transmitted at connection establishment and indicates the protocol capabilities of the system. The SID is enclosed in square brackets and contains the software name, version, and capability flags.

**Format:**
```
[<software>-<version>-<flags>]
```

**Example:**
```
[FBB-7.10-B1FHMS$]
```

### 2.2 Capability Flags

The following flags indicate protocol capabilities:

| Flag | Description |
|------|-------------|
| F | FBB protocol support (required for all FBB modes) |
| B | Binary compressed mode support |
| B1 | Binary compressed mode version 1 with CRC16 |
| B2 | Extended mode with encapsulated messages |
| H | Hierarchical routing support |
| M | MID/BID support |
| S | Simple forwarding |
| $ | Indicates end of flags |

**Important:** The F flag must be present for any FBB protocol operation. A SID with only the B flag (and no F) will be treated as having neither flag present.

### 2.3 SID Exchange

When two BBS systems connect, each sends its SID. The presence of the F flag in both SIDs enables FBB forwarding. If one system lacks the F flag, the systems fall back to standard MBL/RLI forwarding.

## 3. Message Identification

### 3.1 MID/BID Format

Each message is assigned a unique identifier to prevent duplicate forwarding:

- **MID (Message ID):** Assigned to private messages
- **BID (Bulletin ID):** Assigned to bulletins for network-wide deduplication

**Format:**
```
<sequence>_<callsign>
```

**Examples:**
```
24657_F6FBB
2734_FC1GHV
```

The sequence number is typically an incrementing counter maintained by the originating BBS. Combined with the callsign, this creates a globally unique identifier.

### 3.2 BID Usage

When a BBS receives a message proposal containing a BID, it checks its database of previously received BIDs. If the BID exists, the message is rejected to prevent duplicate storage and forwarding.

## 4. Protocol Flow

### 4.1 Connection Sequence

1. Station A connects to Station B
2. Station B sends SID and prompt
3. Station A sends SID followed by first proposal block
4. Station B responds with acceptance/rejection codes
5. Station A sends accepted messages
6. Direction reverses; Station B sends proposals
7. Process continues until both sides send FF (no more messages)
8. Session terminates with FQ

### 4.2 Example Session

```
B: [FBB-7.10-B1FHM$]
B: Station B BBS
B: >
A: [FBB-7.10-B1FHM$]
A: FB P F6FBB FC1GHV FC1MVP 24657_F6FBB 1345
A: FB B AMSAT @WW USERS 12458_F6FBB 2890
A: F>
B: FS +-
A: <message 1 data>
A: ^Z
B: FB P WA1ABC K1XYZ K1XYZ 5678_FC1GHV 456
B: F>
A: FS +
B: <message data>
B: ^Z
B: FF
A: FF
A: FQ
```

## 5. Message Proposals

### 5.1 Proposal Format

All proposal commands begin with F in the first column and end with carriage return.

**Basic proposal format (seven fields required):**
```
FB <type> <sender> <bbs> <recipient> <mid/bid> <size> [<checksum>]
F>
```

| Field | Description |
|-------|-------------|
| FB | Proposal command (FA for ASCII compressed, FC for encapsulated) |
| type | Message type: P (Private) or B (Bulletin) |
| sender | Originating callsign |
| bbs | Destination BBS (@ field) |
| recipient | Recipient callsign |
| mid/bid | Message identifier |
| size | Message size in bytes |
| checksum | Optional hexadecimal checksum |

**Example:**
```
FB P F6FBB FC1GHV FC1MVP 24657_F6FBB 1345
```

### 5.2 Proposal Commands

| Command | Description |
|---------|-------------|
| FA | ASCII compressed message |
| FB | Binary compressed file (or standard proposal in basic mode) |
| FC | Encapsulated message (B2 mode only) |
| F> | End of proposal block |

### 5.3 Proposal Block Limits

- Maximum 5 proposals per block
- Default maximum block size: 10 KB
- All required fields must be present or an error occurs

## 6. Response Codes

### 6.1 FS Response Format

The receiving BBS responds to proposals with an FS line containing one character per proposal:

```
FS <response_codes>
```

**Example:**
```
FS +-+
```

This accepts proposals 1 and 3, rejects proposal 2.

### 6.2 Response Code Table

**Version 0 (Basic) Responses:**

| Code | Description |
|------|-------------|
| + | Accept message |
| - | Reject message (already received or not wanted) |
| = | Defer message (currently receiving on another channel) |

**Version 1 (Extended) Responses:**

| Code | Description |
|------|-------------|
| Y | Accept (equivalent to +) |
| N | Reject (equivalent to -) |
| L | Later/defer (equivalent to =) |
| H | Accept but hold for later delivery |
| R | Reject |
| E | Error in proposal line |
| !offset | Accept from specified byte offset |
| Aoffset | Accept from specified byte offset (alternate syntax) |

The offset capability allows resumption of interrupted transfers in version 1 implementations.

## 7. Message Transfer

### 7.1 ASCII Mode

In basic ASCII mode, messages are transmitted as plain text:

1. Message title (first line)
2. Message body (text)
3. Ctrl-Z (0x1A) terminator

Multiple messages are sent sequentially without blank lines between them:

```
Message 1 Title
Message 1 body text...
^Z
Message 2 Title
Message 2 body text...
^Z
```

### 7.2 Direction Reversal

After transmitting accepted messages, the sending station sends its proposal block or FF if it has no messages. The receiving station then becomes the sender. This bidirectional exchange continues until both sides indicate no more messages with FF.

## 8. Compressed Transfer (B/B1 Mode)

### 8.1 Compression Algorithm

FBB compressed mode uses LZHUF compression, a variant of LZH compression using:

- Lempel-Ziv sliding dictionary compression
- Huffman coding

The algorithm was adapted from Haruhiko Okumura's LZARI via Haruyasu Yoshizaki's LHarc. Open source implementations are available.

### 8.2 Compressed Message Header

**ASCII compressed message (FA) header:**
```
<SOH> <length> <title> <NUL> <offset> <NUL>
```

| Field | Value | Description |
|-------|-------|-------------|
| SOH | 0x01 | Start of header |
| length | 1 byte | Header length |
| title | 1-80 bytes | Message title (ASCII) |
| NUL | 0x00 | Field separator |
| offset | 1-6 bytes | Resume offset (ASCII) |
| NUL | 0x00 | Header terminator |

**Binary file (FB) header:**

Same structure with filename instead of title.

**Note:** French regulations require that titles and filenames remain uncompressed for regulatory inspection.

### 8.3 Data Block Format

```
<STX> <size> <data>
```

| Field | Value | Description |
|-------|-------|-------------|
| STX | 0x02 | Start of data block |
| size | 0x00-0xFF | Byte count (0x00 = 256 bytes) |
| data | 1-256 bytes | Compressed data |

### 8.4 Version 1 First Block Addition

In B1 mode, the first data block prepends:

| Field | Size | Description |
|-------|------|-------------|
| CRC16 | 2 bytes | CRC of uncompressed file (little-endian) |
| Size | 4 bytes | Uncompressed file size (little-endian) |

This enables verification and resume capability.

### 8.5 End of Transfer

```
<EOT> <checksum>
```

| Field | Value | Description |
|-------|-------|-------------|
| EOT | 0x04 | End of transmission |
| checksum | 1 byte | Data checksum |

**Checksum calculation:**

1. Sum all data bytes
2. Take modulo 256
3. Take two's complement

Verification: Sum of all data bytes plus checksum equals zero (mod 256).

## 9. Control Characters Summary

| Character | Hex | Name | Usage |
|-----------|-----|------|-------|
| NUL | 0x00 | Null | Field separator in headers |
| SOH | 0x01 | Start of Header | Begins compressed header |
| STX | 0x02 | Start of Text | Begins data block |
| EOT | 0x04 | End of Transmission | Ends compressed transfer |
| SUB | 0x1A | Substitute (Ctrl-Z) | Ends ASCII message |

## 10. Session Termination Commands

| Command | Description |
|---------|-------------|
| FF | No more messages to send |
| FQ | Request disconnection |

### 10.1 Normal Termination

A normal session ends when both sides have sent FF:

```
A: FF
B: FF
A: FQ
<disconnect>
```

### 10.2 Error Handling

If a required field is missing from a proposal or an unrecoverable error occurs, the session may be terminated abruptly. Implementations should handle disconnection gracefully and be prepared to resume interrupted transfers.

## 11. Extended Mode (B2/B2F)

### 11.1 Overview

B2 mode, also known as B2F (Binary 2 Forwarding), extends the FBB protocol to support:

- Multiple recipients (To, Cc)
- File attachments
- Structured message headers
- Enhanced addressing

This mode is primarily used by Winlink and compatible systems.

### 11.2 FC Proposal Format

B2 mode uses FC proposals for encapsulated messages:

```
FC <type> <id> <usize> <csize>
```

| Field | Description |
|-------|-------------|
| FC | Encapsulated message proposal |
| type | EM (Encapsulated Message) or CM (Control Message) |
| id | Unique identifier (max 12 characters) |
| usize | Uncompressed size in bytes |
| csize | Compressed size in bytes |

Unlike FA/FB proposals, FC proposals do not include sender or recipient addressing—this information is contained within the encapsulated message header.

### 11.3 B2F Message Structure

A B2F encapsulated message contains three parts:

**1. Header:** ASCII text with CR/LF line separators

| Field | Description |
|-------|-------------|
| Mid: | Unique message identifier (max 12 characters) |
| Date: | UTC date/time (YYYY/MM/DD HH:MM) |
| Type: | Message classification (Private, Bulletin, etc.) |
| From: | Sender address |
| To: | Recipient address(es) |
| Cc: | Carbon copy address(es) |
| Subject: | Message subject (max 128 characters) |
| Mbo: | Originating mailbox |
| Body: | Body size in bytes |
| File: | Attachment size and filename (may repeat) |

**2. Body:** ASCII text, separated from header by blank line

**3. Attachments:** Optional binary data

### 11.4 B2F Protocol Extensions

Comment-based extensions (lines beginning with semicolon):

| Extension | Description |
|-----------|-------------|
| ;PQ: | Authentication challenge |
| ;PR: | Authentication response |
| ;FW: | Forward with password hash |
| ;PM: | Pending messages notification |

## 12. Backward Compatibility

The FBB protocol maintains backward compatibility across versions:

- Systems negotiate capabilities via SID exchange
- B2-capable systems fall back to B1/B0/ASCII with older systems
- Non-FBB systems use standard MBL/RLI forwarding

When connecting to a system without FBB capability, implementations should detect the absence of the F flag and use appropriate fallback protocols.

## 13. Implementation Notes

### 13.1 Block Size Considerations

The default 10 KB block size balances efficiency with error recovery. On reliable links, larger blocks improve throughput. On noisy links, smaller blocks reduce retransmission overhead.

### 13.2 Pipeline Effect

The protocol's bidirectional block transfer creates a pipeline effect that optimizes throughput on high-latency links (satellite, long digipeater chains). While one station transmits data, the other prepares its next proposal block.

### 13.3 BID Database Management

BBS systems must maintain a database of received BIDs to prevent duplicate bulletins. This database should be periodically pruned of old entries to manage storage requirements while maintaining sufficient history to prevent duplicates.

## References

1. F6FBB Official Documentation: https://www.f6fbb.org/protocole.html
2. F6FBB Forward Protocol Documentation: https://www.f6fbb.org/fbbdoc/docfwpro.htm
3. Packet-Radio.net FBB Protocol: https://packet-radio.net/fbb-forward-protocol/
4. Winlink B2F Specification: https://winlink.org/B2F
5. ARSFI Winlink Compression Source: https://github.com/ARSFI/Winlink-Compression

## Document History

| Date | Description |
|------|-------------|
| 1986 | Original FBB protocol developed by F6FBB |
| — | Compressed forwarding (B/B1) added |
| — | B2F extension developed for Winlink |
| 2025 | This markdown document compiled from public sources |
