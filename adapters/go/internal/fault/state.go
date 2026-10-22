package fault

import "sync"

// Fault kinds and modes. The mode strings are the ones harness/lib/classify.mjs matches.
const (
	KindSavepoint = "savepoint"
	KindRoot      = "root"
	KindCommit    = "commit"

	ModeClientReject = "client-reject"
	ModeRewrite      = "rewrite"
	ModeReplyLost    = "reply-lost"
)

// Note is one transaction-control statement the pgx tracer observed.
// It is diagnostic. Classification does not read it.
type Note struct {
	SQL        string `json:"sql"`
	CommandTag string `json:"command_tag,omitempty"`
	Error      string `json:"error,omitempty"`
}

// State is one armed client-side fault, plus the statement notes from the tracer.
// Category C and D faults are injections in this process, not network failures.
type State struct {
	mu         sync.Mutex
	kind       string
	mode       string
	armed      bool
	fired      int
	pid        int
	withheld   []string
	rewritten  []string
	replyCodes []string
	discarded  string
	hookError  string
	notes      []Note
	onFire     func() error
}

// SetFire installs the after-fault checkpoint. It runs from the tracer, before the
// caller of pgx.Conn.Exec sees the error. Nil means the fault does not checkpoint
// (category D has no after-fault checkpoint).
func (s *State) SetFire(fn func() error) {
	s.mu.Lock()
	s.onFire = fn
	s.mu.Unlock()
}

// SetPID is the backend the after-fault checkpoint reports.
func (s *State) SetPID(pid int) {
	s.mu.Lock()
	s.pid = pid
	s.mu.Unlock()
}

// Arm arms one fault. A later Take or Fire consumes it.
func (s *State) Arm(kind, mode string) {
	s.mu.Lock()
	s.kind = kind
	s.mode = mode
	s.armed = true
	s.mu.Unlock()
}

// Disarm stops a fault that has not fired yet. A fault that already fired keeps
// its mode so the result can report it.
func (s *State) Disarm() {
	s.mu.Lock()
	s.armed = false
	s.mu.Unlock()
}

// Take consumes a matching armed fault and counts it fired. The caller checkpoints.
func (s *State) Take(kind, mode string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.armed || s.kind != kind || s.mode != mode {
		return false
	}
	s.armed = false
	s.fired++
	return true
}

// Peek reports whether an armed fault matches, without consuming it.
func (s *State) Peek(kind, mode string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.armed && s.kind == kind && s.mode == mode
}

// Withhold records the SQL that was not sent and fires the checkpoint.
func (s *State) Withhold(sql string) {
	s.mu.Lock()
	s.withheld = append(s.withheld, normalize(sql))
	s.mu.Unlock()
	s.fire()
}

// NoteRewrite records a rewritten statement. The checkpoint waits until the server has answered.
func (s *State) NoteRewrite(original string) {
	s.mu.Lock()
	s.rewritten = append(s.rewritten, "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint")
	s.withheld = append(s.withheld, normalize(original))
	s.mu.Unlock()
}

// NoteReply records PostgreSQL's SQLSTATE for a rewritten statement, then fires.
func (s *State) NoteReply(code string) {
	s.mu.Lock()
	if code == "" {
		code = "error"
	}
	s.replyCodes = append(s.replyCodes, code)
	s.mu.Unlock()
	s.fire()
}

// NoteDiscarded records the parsed commit result that category D then hid.
func (s *State) NoteDiscarded(result string) {
	s.mu.Lock()
	s.discarded = result
	s.mu.Unlock()
}

// AddNote records a transaction-control statement the tracer saw.
func (s *State) AddNote(n Note) {
	s.mu.Lock()
	s.notes = append(s.notes, n)
	s.mu.Unlock()
}

func (s *State) fire() {
	s.mu.Lock()
	if !s.armed {
		s.mu.Unlock()
		return
	}
	s.armed = false
	s.fired++
	fn := s.onFire
	s.mu.Unlock()
	if fn == nil {
		return
	}
	if err := fn(); err != nil {
		s.mu.Lock()
		s.hookError = err.Error()
		s.mu.Unlock()
	}
}

// Notes returns the tracer's statement notes.
func (s *State) Notes() []Note {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]Note, len(s.notes))
	copy(out, s.notes)
	return out
}

// Report is the steps.fault object. fired is zero when the fault was not armed.
func (s *State) Report() map[string]any {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.mode == "" && s.fired == 0 {
		return nil
	}
	out := map[string]any{
		"mode":      s.mode,
		"fired":     s.fired,
		"injection": "client-side",
	}
	if s.withheld != nil {
		out["withheld"] = append([]string(nil), s.withheld...)
	}
	if len(s.rewritten) > 0 {
		out["rewritten"] = append([]string(nil), s.rewritten...)
	}
	if len(s.replyCodes) > 0 {
		out["reply_codes"] = append([]string(nil), s.replyCodes...)
	}
	if s.discarded != "" {
		out["discarded_result"] = s.discarded
	}
	if s.hookError != "" {
		out["hook_error"] = s.hookError
	}
	return out
}
