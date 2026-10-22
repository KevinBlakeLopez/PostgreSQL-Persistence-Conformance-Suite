// Package protocol is PPCS adapter protocol version 1 on stdin and stdout.
// A checkpoint exchange failure is a protocol error, never a transaction outcome.
package protocol

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"
)

const Version = 1

// ProtocolError is a failed checkpoint exchange. Callers must not map it to a transaction outcome.
type ProtocolError struct{ Msg string }

func (e *ProtocolError) Error() string { return e.Msg }

type Connection struct {
	Host            string `json:"host"`
	Port            int    `json:"port"`
	User            string `json:"user"`
	Password        string `json:"password"`
	Database        string `json:"database"`
	ApplicationName string `json:"application_name"`
}

type Settings struct {
	PoolMax   int    `json:"pool_max"`
	SettleMS  int    `json:"settle_ms"`
	BoundMS   int    `json:"bound_ms"`
	Isolation string `json:"isolation_level"`
}

type Case struct {
	ID       string   `json:"id"`
	Family   string   `json:"family"`
	Version  string   `json:"version"`
	Title    string   `json:"title"`
	Settings Settings `json:"settings"`
}

// Message is one protocol object. Unused fields stay empty.
type Message struct {
	PPCS       int               `json:"ppcs"`
	Type       string            `json:"type"`
	Case       Case              `json:"case"`
	Mode       string            `json:"mode"`
	Repetition int               `json:"repetition"`
	Connection Connection        `json:"connection"`
	Markers    map[string]string `json:"markers"`
	Name       string            `json:"name"`
}

// Protocol reads the runner's messages and writes the adapter's.
type Protocol struct {
	in   *bufio.Reader
	enc  *json.Encoder
	mu   sync.Mutex
	halt bool
}

func New() *Protocol {
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	return &Protocol{in: bufio.NewReaderSize(os.Stdin, 1<<20), enc: enc}
}

// Halt makes a checkpoint that has not started fail instead of writing. An in-flight exchange finishes.
func (p *Protocol) Halt() {
	p.mu.Lock()
	p.halt = true
	p.mu.Unlock()
}

func (p *Protocol) Read() (Message, error) {
	for {
		line, err := p.in.ReadBytes('\n')
		if err != nil {
			if err == io.EOF {
				return Message{}, &ProtocolError{Msg: "the runner closed the protocol stream"}
			}
			return Message{}, &ProtocolError{Msg: "reading the protocol stream failed: " + err.Error()}
		}
		if len(line) == 0 || (len(line) == 1 && line[0] == '\n') {
			continue
		}
		var msg Message
		if err := json.Unmarshal(line, &msg); err != nil {
			continue
		}
		if msg.PPCS != Version {
			continue
		}
		return msg, nil
	}
}

func (p *Protocol) Send(fields map[string]any) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	body := map[string]any{"ppcs": Version}
	for k, v := range fields {
		body[k] = v
	}
	if err := p.enc.Encode(body); err != nil {
		return &ProtocolError{Msg: "writing the protocol stream failed: " + err.Error()}
	}
	return nil
}

// Checkpoint reports name and blocks until the matching resume.
// xid, pid, and isolation are omitted when empty. pid 0 is omitted.
func (p *Protocol) Checkpoint(name, xid string, pid int, isolation string) error {
	p.mu.Lock()
	if p.halt {
		p.mu.Unlock()
		return &ProtocolError{Msg: fmt.Sprintf("checkpoint %q was not sent: the wait for this unit was given up", name)}
	}
	body := map[string]any{"ppcs": Version, "type": "checkpoint", "name": name}
	if pid != 0 {
		body["pid"] = pid
	}
	if xid != "" {
		body["xid"] = xid
	}
	if isolation != "" {
		body["transaction_isolation"] = isolation
	}
	if err := p.enc.Encode(body); err != nil {
		p.mu.Unlock()
		return &ProtocolError{Msg: "writing the protocol stream failed: " + err.Error()}
	}
	p.mu.Unlock()

	resume, err := p.Read()
	if err != nil {
		return err
	}
	if resume.Type != "resume" || resume.Name != name {
		return &ProtocolError{Msg: fmt.Sprintf("expected resume for checkpoint %q", name)}
	}
	return nil
}

// IsProtocol reports whether err is a protocol failure, including through wrapping.
func IsProtocol(err error) bool {
	var pe *ProtocolError
	return err != nil && asProtocol(err, &pe)
}

func asProtocol(err error, target **ProtocolError) bool {
	for err != nil {
		if pe, ok := err.(*ProtocolError); ok {
			*target = pe
			return true
		}
		u, ok := err.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}
