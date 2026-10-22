// Minimal reproduction: GORM's PostgreSQL dialector returns a nil error from
// RollbackTo when PostgreSQL rejects the statement.
//
// Not an upstream filing. Run against the disposable PPCS server only:
//
//	go run -mod=readonly ./cmd/gorm-rollback-repro /path/to/.ppcs-instance.json
package main

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/stdlib"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type instance struct {
	Token    string `json:"token"`
	Host     string `json:"host"`
	Port     int    `json:"port"`
	User     string `json:"user"`
	Password string `json:"password"`
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: gorm-rollback-repro .ppcs-instance.json")
		os.Exit(2)
	}
	raw, err := os.ReadFile(os.Args[1])
	if err != nil {
		fatal(err)
	}
	var inst instance
	if err := json.Unmarshal(raw, &inst); err != nil {
		fatal(err)
	}
	admin, err := sql.Open("pgx", dsn(inst, "postgres"))
	if err != nil {
		fatal(err)
	}
	defer admin.Close()
	var cluster string
	if err := admin.QueryRow("select current_setting('cluster_name')").Scan(&cluster); err != nil {
		fatal(err)
	}
	if cluster != inst.Token {
		fatal(fmt.Errorf("cluster_name does not match this .ppcs-instance.json"))
	}
	const name = "ppcs_gorm_rollback_repro"
	_, _ = admin.Exec("drop database if exists " + name)
	if _, err := admin.Exec("create database " + name); err != nil {
		fatal(err)
	}
	defer admin.Exec("drop database if exists " + name)

	sqlDB, err := sql.Open("pgx", dsn(inst, name))
	if err != nil {
		fatal(err)
	}
	defer sqlDB.Close()
	gdb, err := gorm.Open(postgres.New(postgres.Config{Conn: sqlDB}), &gorm.Config{Logger: logger.Discard})
	if err != nil {
		fatal(err)
	}
	if err := gdb.Exec("create table item (id serial primary key, name text)").Error; err != nil {
		fatal(err)
	}
	tx := gdb.Begin()
	if tx.Error != nil {
		fatal(tx.Error)
	}
	if err := tx.SavePoint("sp").Error; err != nil {
		fatal(err)
	}
	if err := tx.Exec("insert into item (name) values (?)", "kept").Error; err != nil {
		fatal(err)
	}
	rb := tx.RollbackTo("no_such_savepoint")
	fmt.Printf("RollbackTo().Error == nil: %v\n", rb.Error == nil)
	if rb.Error != nil {
		fmt.Printf("RollbackTo().Error: %v\n", rb.Error)
	}
	commitErr := tx.Commit().Error
	fmt.Printf("Commit().Error: %v\n", commitErr)
	fmt.Printf("errors.Is(Commit().Error, pgx.ErrTxCommitRollback): %v\n", errors.Is(commitErr, pgx.ErrTxCommitRollback))
	var pgErr *pgconn.PgError
	if errors.As(commitErr, &pgErr) {
		fmt.Printf("commit SQLSTATE: %s\n", pgErr.Code)
	}
	var count int
	if err := gdb.Raw("select count(*) from item").Scan(&count).Error; err != nil {
		fatal(err)
	}
	fmt.Printf("rows visible after Commit: %d\n", count)
}

func dsn(inst instance, database string) string {
	return fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		inst.Host, inst.Port, inst.User, inst.Password, database)
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}

// Register the pgx stdlib driver. sql.Open("pgx") needs the driver's init.
var _ = stdlib.GetDefaultDriver
