// Package pgcfg builds the pgx connection configuration shared by the three adapters.
package pgcfg

import (
	"context"
	"fmt"
	"net"

	"github.com/jackc/pgx/v5"
	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/protocol"
)

// Builder produces a fresh ConnConfig. pgx.ConnectConfig takes ownership of the
// config it is given, so each dial calls Config again.
type Builder struct {
	Connection protocol.Connection
	State      *fault.State
	Tracer     pgx.QueryTracer
}

func (b Builder) Config() (*pgx.ConnConfig, error) {
	cfg, err := pgx.ParseConfig("sslmode=disable")
	if err != nil {
		return nil, err
	}
	cfg.Host = b.Connection.Host
	cfg.Port = uint16(b.Connection.Port)
	cfg.User = b.Connection.User
	cfg.Password = b.Connection.Password
	cfg.Database = b.Connection.Database
	if cfg.RuntimeParams == nil {
		cfg.RuntimeParams = map[string]string{}
	}
	if b.Connection.ApplicationName != "" {
		cfg.RuntimeParams["application_name"] = b.Connection.ApplicationName
	}
	cfg.Tracer = b.Tracer
	state := b.State
	cfg.DialFunc = func(ctx context.Context, network, addr string) (net.Conn, error) {
		var d net.Dialer
		c, err := d.DialContext(ctx, network, addr)
		if err != nil {
			return nil, err
		}
		return fault.Wrap(c, state), nil
	}
	return cfg, nil
}

func (b Builder) String() string {
	return fmt.Sprintf("%s:%d/%s", b.Connection.Host, b.Connection.Port, b.Connection.Database)
}
