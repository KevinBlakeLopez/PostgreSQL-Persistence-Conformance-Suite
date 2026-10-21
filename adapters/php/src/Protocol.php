<?php

declare(strict_types=1);

namespace Ppcs;

// PPCS adapter protocol version 1 (docs/protocol.md). Newline-delimited JSON
// on stdin and stdout. Lines without "ppcs": 1 are not protocol messages.
final class Protocol
{
    public function read(): array
    {
        while (($line = fgets(STDIN)) !== false) {
            $line = trim($line);
            if ($line === '') {
                continue;
            }
            try {
                $msg = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
            } catch (\JsonException $e) {
                throw new ProtocolException('the runner sent a line that is not JSON');
            }
            if (!is_array($msg) || ($msg['ppcs'] ?? null) !== 1) {
                continue;
            }

            return $msg;
        }
        throw new ProtocolException('the runner closed the protocol stream');
    }

    public function send(array $msg): void
    {
        $msg['ppcs'] = 1;
        $json = json_encode($msg, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        if (fwrite(STDOUT, $json."\n") === false) {
            throw new ProtocolException('could not write a protocol message');
        }
        fflush(STDOUT);
    }

    /**
     * Report a checkpoint and wait for the matching resume.
     * pid and xid are omitted from the payload when unknown, except that pid is
     * sent as null when the case still needs the checkpoint.
     *
     * @return array<string, mixed>
     */
    public function checkpoint(string $name, ?string $xid, ?int $pid, ?string $isolation = null): array
    {
        $msg = ['type' => 'checkpoint', 'name' => $name, 'pid' => $pid];
        if ($xid !== null) {
            $msg['xid'] = $xid;
        }
        if ($isolation !== null) {
            $msg['transaction_isolation'] = $isolation;
        }
        $this->send($msg);
        $resume = $this->read();
        if (($resume['type'] ?? null) !== 'resume' || ($resume['name'] ?? null) !== $name) {
            throw new ProtocolException('expected resume for checkpoint "'.$name.'"');
        }

        return $resume;
    }
}
