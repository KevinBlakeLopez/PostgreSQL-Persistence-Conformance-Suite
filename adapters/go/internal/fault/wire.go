package fault

import (
	"encoding/binary"
	"net"
)

const rewrittenSavepoint = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint"

// Conn wraps a cleartext PostgreSQL connection. When a rewrite fault is armed,
// a simple-query message whose SQL is ROLLBACK TO SAVEPOINT is replaced before
// the bytes reach the server. Every other write is forwarded unchanged.
// pgx sends argument-free statements, including ROLLBACK TO, with the simple
// query protocol ('Q'). Extended-protocol messages are not rewritten.
type Conn struct {
	net.Conn
	state *State
	buf   []byte
}

// Wrap returns a connection that can rewrite one armed statement.
func Wrap(c net.Conn, state *State) net.Conn {
	return &Conn{Conn: c, state: state}
}

func (c *Conn) Write(p []byte) (int, error) {
	if c.state == nil || !c.state.Peek(KindSavepoint, ModeRewrite) {
		if len(c.buf) == 0 {
			return c.Conn.Write(p)
		}
	}
	c.buf = append(c.buf, p...)
	for {
		msg, rest, ok := popQuery(c.buf)
		if !ok {
			// Not a complete simple query. Forward what we have if it cannot be one.
			if len(c.buf) > 0 && c.buf[0] != 'Q' {
				_, err := c.Conn.Write(c.buf)
				c.buf = nil
				if err != nil {
					return 0, err
				}
			}
			return len(p), nil
		}
		c.buf = rest
		sql := querySQL(msg)
		out := msg
		if c.state.Peek(KindSavepoint, ModeRewrite) && IsRollbackTo(sql) {
			c.state.NoteRewrite(sql)
			out = buildQuery(rewrittenSavepoint)
		}
		if _, err := c.Conn.Write(out); err != nil {
			return 0, err
		}
		if len(c.buf) == 0 {
			return len(p), nil
		}
	}
}

func popQuery(buf []byte) (msg, rest []byte, ok bool) {
	if len(buf) < 5 || buf[0] != 'Q' {
		return nil, buf, false
	}
	n := int(binary.BigEndian.Uint32(buf[1:5]))
	if n < 4 {
		return nil, buf, false
	}
	total := 1 + n
	if len(buf) < total {
		return nil, buf, false
	}
	return buf[:total], buf[total:], true
}

func querySQL(msg []byte) string {
	// 'Q' + int32 length + SQL + NUL. Length includes itself and the NUL.
	if len(msg) < 6 {
		return ""
	}
	payload := msg[5:]
	if payload[len(payload)-1] == 0 {
		payload = payload[:len(payload)-1]
	}
	return string(payload)
}

func buildQuery(sql string) []byte {
	// length = 4 bytes of length + sql + NUL
	n := 4 + len(sql) + 1
	buf := make([]byte, 1+n)
	buf[0] = 'Q'
	binary.BigEndian.PutUint32(buf[1:5], uint32(n))
	copy(buf[5:], sql)
	buf[len(buf)-1] = 0
	return buf
}
