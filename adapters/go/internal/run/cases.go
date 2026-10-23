package run

import (
	"context"
	"errors"
	"fmt"
	"time"

	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/protocol"
)

// Result is one completed case, before the implicit after-end checkpoint.
type Result struct {
	Reported    string
	Basis       string
	Contract    string
	APIError    *APIError
	Steps       map[string]any
	Form        string
	Diagnostics map[string]any
}

func (r Result) Fields() map[string]any {
	out := map[string]any{
		"type":     "result",
		"status":   "completed",
		"reported": r.Reported,
		"basis":    r.Basis,
		"contract": r.Contract,
	}
	if r.APIError != nil {
		out["api_error"] = r.APIError
	}
	if r.Steps != nil {
		out["steps"] = r.Steps
	}
	if r.Form != "" {
		out["form"] = r.Form
	}
	if r.Diagnostics != nil {
		out["diagnostics"] = r.Diagnostics
	}
	return out
}

// Env is the case's protocol session.
type Env struct {
	P   *protocol.Protocol
	DB  DB
	Msg protocol.Message
	PID int
}

func (e *Env) CP(name, xid string, pid int, isolation string) error {
	if pid != 0 {
		e.PID = pid
		e.DB.Fault().SetPID(pid)
	}
	return e.P.Checkpoint(name, xid, pid, isolation)
}

func (e *Env) finish(c Completion, steps map[string]any, form string) (Result, error) {
	if protocol.IsProtocol(c.BodyErr) {
		return Result{}, c.BodyErr
	}
	if protocol.IsProtocol(c.BeginErr) || protocol.IsProtocol(c.CommitErr) || protocol.IsProtocol(c.RollbackErr) {
		for _, err := range []error{c.BeginErr, c.CommitErr, c.RollbackErr} {
			if protocol.IsProtocol(err) {
				return Result{}, err
			}
		}
	}
	reported, basis, api := Report(e.DB.Surface(), c)
	if steps == nil {
		steps = map[string]any{}
	}
	if rep := e.DB.Fault().Report(); rep != nil && steps["fault"] == nil {
		steps["fault"] = rep
	}
	diag := map[string]any{}
	if notes := e.DB.Fault().Notes(); len(notes) > 0 {
		diag["statements"] = notes
	}
	if e.DB.Reconnected() {
		diag["reconnected"] = true
	}
	return Result{
		Reported:    reported,
		Basis:       basis,
		Contract:    contractFor(e.DB.Surface()),
		APIError:    api,
		Steps:       steps,
		Form:        form,
		Diagnostics: diag,
	}, nil
}

// Execute runs the case in msg. It does not send after-end.
func Execute(p *protocol.Protocol, db DB, msg protocol.Message) (Result, error) {
	e := &Env{P: p, DB: db, Msg: msg}
	if faultCheckpoint(msg.Case.ID) {
		db.Fault().SetFire(func() error {
			return e.P.Checkpoint("after-fault", "", e.PID, "")
		})
	}
	ctx := context.Background()
	switch msg.Case.ID {
	case "CTL-01.commit":
		return e.commit(ctx)
	case "CTL-01.rollback":
		return e.rollback(ctx)
	case "TX-01A.caught-error-then-commit":
		return e.caught(ctx)
	case "TX-01B.conn-lost-before-commit":
		return e.connLost(ctx)
	case "TX-01B.commit-reply-discarded":
		return e.replyLost(ctx)
	case "TX-01B.commit-reply-unseen":
		return e.unseen(ctx)
	case "TX-02.savepoint-rollback-not-sent":
		return e.savepoint(ctx, "not-sent")
	case "TX-02.savepoint-rollback-rejected":
		return e.savepoint(ctx, "rejected")
	case "TX-02.conn-lost-before-savepoint-rollback":
		return e.savepoint(ctx, "conn-lost")
	case "TX-03.rollback-not-sent":
		return e.reuse(ctx, "rollback-not-sent")
	case "TX-03.statement-error-rollback-not-sent":
		return e.reuse(ctx, "statement-error")
	case "TX-03.conn-lost-in-transaction":
		return e.reuse(ctx, "conn-lost")
	case "TX-04.nested-failure-contained":
		return e.nested(ctx, "nested-fails")
	case "TX-04.nested-released-outer-rollback":
		return e.nested(ctx, "outer-fails")
	case "TX-05.managed-serializable", "TX-05.explicit-serializable":
		return e.isolation(ctx)
	default:
		return Result{}, fmt.Errorf("no case implementation for %s", msg.Case.ID)
	}
}

func faultCheckpoint(id string) bool {
	switch id {
	case "TX-02.savepoint-rollback-not-sent", "TX-02.savepoint-rollback-rejected",
		"TX-03.rollback-not-sent", "TX-03.statement-error-rollback-not-sent":
		return true
	default:
		return false
	}
}

func (e *Env) marker(name string) (string, error) {
	v, ok := e.Msg.Markers[name]
	if !ok || v == "" {
		return "", fmt.Errorf("the case did not provide marker %s", name)
	}
	return v, nil
}

func (e *Env) commit(ctx context.Context) (Result, error) {
	name, err := e.marker("tx")
	if err != nil {
		return Result{}, err
	}
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		return e.CP("before-end", xid, pid, "")
	})
	return e.finish(c, nil, "")
}

func (e *Env) rollback(ctx context.Context) (Result, error) {
	name, err := e.marker("tx")
	if err != nil {
		return Result{}, err
	}
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		if err := e.CP("before-end", xid, pid, ""); err != nil {
			return err
		}
		return ErrApplication
	})
	return e.finish(c, nil, "")
}

func (e *Env) caught(ctx context.Context) (Result, error) {
	name, err := e.marker("tx")
	if err != nil {
		return Result{}, err
	}
	var violation *APIError
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		if err := e.CP("after-write", xid, pid, ""); err != nil {
			return err
		}
		err = tx.InsertTaken(ctx)
		violation = ErrorInfo(err)
		if err == nil {
			return fmt.Errorf("the duplicate insert did not raise")
		}
		return e.CP("before-end", "", pid, "")
	})
	steps := map[string]any{}
	if violation != nil {
		steps["violation"] = violation
	}
	return e.finish(c, steps, "")
}

func (e *Env) connLost(ctx context.Context) (Result, error) {
	return e.endAfter("before-end", true)
}

func (e *Env) unseen(ctx context.Context) (Result, error) {
	return e.endAfter("before-end", false)
}

func (e *Env) replyLost(ctx context.Context) (Result, error) {
	name, err := e.marker("tx")
	if err != nil {
		return Result{}, err
	}
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		if err := e.CP("before-end", xid, pid, ""); err != nil {
			return err
		}
		e.DB.Fault().Arm(fault.KindCommit, fault.ModeReplyLost)
		return nil
	})
	return e.finish(c, map[string]any{}, "")
}

func (e *Env) endAfter(checkpoint string, settle bool) (Result, error) {
	name, err := e.marker("tx")
	if err != nil {
		return Result{}, err
	}
	ctx := context.Background()
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		if err := e.CP(checkpoint, xid, pid, ""); err != nil {
			return err
		}
		if settle {
			ms := e.Msg.Case.Settings.SettleMS
			if ms <= 0 {
				ms = 100
			}
			time.Sleep(time.Duration(ms) * time.Millisecond)
		}
		return nil
	})
	return e.finish(c, nil, "")
}

func (e *Env) savepoint(ctx context.Context, kind string) (Result, error) {
	outer, err := e.marker("outer")
	if err != nil {
		return Result{}, err
	}
	inner, err := e.marker("inner")
	if err != nil {
		return Result{}, err
	}
	var nestedErr, rbErr error
	var pid int
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, outer); err != nil {
			return err
		}
		xid, got, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		pid = got
		if err := e.CP("outer-after-write", xid, pid, ""); err != nil {
			return err
		}
		nestedErr, rbErr = tx.Nested(ctx, func(innerTx Tx) error {
			if err := innerTx.InsertItem(ctx, inner); err != nil {
				return err
			}
			if err := e.CP("inner-after-write", "", pid, ""); err != nil {
				return err
			}
			switch kind {
			case "not-sent":
				e.DB.Fault().Arm(fault.KindSavepoint, fault.ModeClientReject)
			case "rejected":
				e.DB.Fault().Arm(fault.KindSavepoint, fault.ModeRewrite)
			case "conn-lost":
				ms := e.Msg.Case.Settings.SettleMS
				if ms <= 0 {
					ms = 100
				}
				time.Sleep(time.Duration(ms) * time.Millisecond)
			}
			return ErrNested
		})
		if protocol.IsProtocol(nestedErr) {
			return nestedErr
		}
		if protocol.IsProtocol(rbErr) {
			return rbErr
		}
		return nil
	})
	if err := e.CP("after-outer", "", pid, ""); err != nil {
		return Result{}, err
	}
	nested := map[string]any{"caught": nestedErr != nil}
	if nestedErr != nil {
		nested["error"] = ErrorInfo(nestedErr)
	}
	if rbErr != nil {
		nested["rollback_error"] = ErrorInfo(rbErr)
	} else {
		for _, note := range e.DB.Fault().Notes() {
			if fault.IsRollbackTo(note.SQL) && note.Error != "" {
				nested["driver_rollback_error"] = note.Error
				break
			}
		}
	}
	steps := map[string]any{"nested": nested}
	if kind != "conn-lost" {
		if rep := e.DB.Fault().Report(); rep != nil {
			steps["fault"] = rep
		}
	}
	return e.finish(c, steps, e.DB.SavepointForm())
}

func (e *Env) reuse(ctx context.Context, kind string) (Result, error) {
	doomed, err := e.marker("doomed")
	if err != nil {
		return Result{}, err
	}
	next, err := e.marker("next")
	if err != nil {
		return Result{}, err
	}
	var violation *APIError
	var pid1 int
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, doomed); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		pid1 = pid
		if err := e.CP("unit1-after-write", xid, pid, ""); err != nil {
			return err
		}
		if kind == "conn-lost" {
			ms := e.Msg.Case.Settings.SettleMS
			if ms <= 0 {
				ms = 100
			}
			time.Sleep(time.Duration(ms) * time.Millisecond)
		} else {
			e.DB.Fault().Arm(fault.KindRoot, fault.ModeClientReject)
		}
		if kind == "statement-error" {
			err := tx.InsertTaken(ctx)
			violation = ErrorInfo(err)
			if err == nil {
				return fmt.Errorf("the duplicate insert did not raise")
			}
			return err
		}
		return ErrUnit
	})
	e.DB.Fault().Disarm()
	if err := e.CP("after-unit1", "", pid1, ""); err != nil {
		return Result{}, err
	}
	unit2, pid2, uerr := e.unit2(next)
	if uerr != nil {
		return Result{}, uerr
	}
	steps := map[string]any{
		"unit2": unit2,
		"reuse": map[string]any{
			"unit1_pid":    pid1,
			"unit2_pid":    pid2,
			"same_backend": pid1 != 0 && pid1 == pid2,
			"reconnected":  e.DB.Reconnected(),
		},
	}
	if violation != nil {
		steps["violation"] = violation
	}
	if c.BodyErr != nil && !protocol.IsProtocol(c.BodyErr) {
		steps["body_error"] = ErrorInfo(c.BodyErr)
	}
	if c.RollbackErr != nil && !protocol.IsProtocol(c.RollbackErr) {
		steps["cleanup_error"] = ErrorInfo(c.RollbackErr)
	}
	if kind != "conn-lost" {
		if rep := e.DB.Fault().Report(); rep != nil {
			steps["fault"] = rep
		}
	}
	return e.finish(c, steps, e.DB.NextUnitForm())
}

func (e *Env) unit2(name string) (map[string]any, int, error) {
	bound := e.Msg.Case.Settings.BoundMS
	if bound <= 0 {
		bound = 5000
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(bound)*time.Millisecond)
	defer cancel()
	start := time.Now()
	var pid2 int
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		xid, pid, _, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		pid2 = pid
		return e.CP("unit2-after-write", xid, pid, "")
	})
	elapsed := int(time.Since(start).Milliseconds())
	deadline := errors.Is(c.BeginErr, context.DeadlineExceeded) || errors.Is(c.BodyErr, context.DeadlineExceeded) || errors.Is(c.CommitErr, context.DeadlineExceeded)
	if protocol.IsProtocol(c.BodyErr) || protocol.IsProtocol(c.BeginErr) || protocol.IsProtocol(c.CommitErr) || protocol.IsProtocol(c.RollbackErr) {
		for _, err := range []error{c.BodyErr, c.BeginErr, c.CommitErr, c.RollbackErr} {
			if protocol.IsProtocol(err) {
				return nil, pid2, err
			}
		}
	}
	if deadline && pid2 == 0 {
		return map[string]any{"outcome": "pending", "elapsed_ms": elapsed, "reported": "pending"}, 0, nil
	}
	reported, _, api := Report(e.DB.Surface(), c)
	out := map[string]any{"outcome": "completed", "elapsed_ms": elapsed, "reported": reported}
	if api != nil {
		out["api_error"] = api
	}
	return out, pid2, nil
}

func (e *Env) nested(ctx context.Context, variant string) (Result, error) {
	outer, err := e.marker("outer")
	if err != nil {
		return Result{}, err
	}
	inner, err := e.marker("inner")
	if err != nil {
		return Result{}, err
	}
	var caught, completed bool
	c := e.DB.Run(ctx, "", func(tx Tx) error {
		if err := tx.InsertItem(ctx, outer); err != nil {
			return err
		}
		fnErr, _ := tx.Nested(ctx, func(innerTx Tx) error {
			if err := innerTx.InsertItem(ctx, inner); err != nil {
				return err
			}
			xid, pid, _, err := innerTx.Identify(ctx)
			if err != nil {
				return err
			}
			if err := e.CP("inner-after-write", xid, pid, ""); err != nil {
				return err
			}
			if variant == "nested-fails" {
				return ErrNested
			}
			return nil
		})
		if protocol.IsProtocol(fnErr) {
			return fnErr
		}
		if variant == "nested-fails" {
			caught = fnErr != nil
			return nil
		}
		completed = fnErr == nil
		if fnErr != nil {
			return fnErr
		}
		return ErrOuter
	})
	steps := map[string]any{"nested": map[string]any{"caught": caught, "completed": completed}}
	return e.finish(c, steps, e.DB.SavepointForm())
}

func (e *Env) isolation(ctx context.Context) (Result, error) {
	name, err := e.marker("tx")
	if err != nil {
		return Result{}, err
	}
	level := e.Msg.Case.Settings.Isolation
	if level == "" {
		level = "serializable"
	}
	c := e.DB.Run(ctx, level, func(tx Tx) error {
		if err := tx.InsertItem(ctx, name); err != nil {
			return err
		}
		if err := tx.ReadItem(ctx, name); err != nil {
			return err
		}
		xid, pid, iso, err := tx.Identify(ctx)
		if err != nil {
			return err
		}
		return e.CP("after-read", xid, pid, iso)
	})
	steps := map[string]any{"isolation_request": e.DB.IsolationAPI(), "requested": level}
	if c.BeginErr != nil && !protocol.IsProtocol(c.BeginErr) {
		base := e.DB.Run(ctx, "", func(tx Tx) error {
			xid, pid, _, err := tx.Identify(ctx)
			if err != nil {
				return err
			}
			return e.CP("baseline", xid, pid, "")
		})
		if base.BeginErr != nil || base.CommitErr != nil || (base.BodyErr != nil && !protocol.IsProtocol(base.BodyErr)) {
			err := base.BeginErr
			if err == nil {
				err = base.BodyErr
			}
			if err == nil {
				err = base.CommitErr
			}
			steps["baseline"] = map[string]any{"error": ErrorInfo(err)}
		} else if !protocol.IsProtocol(base.BodyErr) {
			reported, _, _ := Report(e.DB.Surface(), base)
			steps["baseline_reported"] = reported
		}
		c.CommitCalled = false
		c.CommitErr = nil
		c.BodyErr = nil
	}
	return e.finish(c, steps, e.DB.IsolationAPI()+". The marker is inserted and read back in that transaction.")
}
