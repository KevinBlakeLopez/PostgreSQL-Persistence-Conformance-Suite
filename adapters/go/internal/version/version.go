package version

import (
	"runtime"
	"runtime/debug"
)

func Go() string { return runtime.Version() }

func Module(path string) string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unknown"
	}
	for _, m := range info.Deps {
		if m.Path == path {
			if m.Replace != nil && m.Replace.Version != "" {
				return m.Replace.Version
			}
			return m.Version
		}
	}
	return "unknown"
}
