package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

var defaultProjectRoot string

func main() {
	root, err := projectRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, "codexswitch:", err)
		os.Exit(1)
	}

	python, err := pythonBinary(root)
	if err != nil {
		fmt.Fprintln(os.Stderr, "codexswitch:", err)
		os.Exit(1)
	}

	backend := filepath.Join(root, "bin", "codexswitch")
	args := append([]string{backend}, os.Args[1:]...)
	cmd := exec.Command(python, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(), "CODEXSWITCH_HOME="+root)

	if err := cmd.Run(); err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			os.Exit(exitErr.ExitCode())
		}
		fmt.Fprintln(os.Stderr, "codexswitch:", err)
		os.Exit(1)
	}
}

func projectRoot() (string, error) {
	candidates := []string{}
	if env := os.Getenv("CODEXSWITCH_HOME"); env != "" {
		candidates = append(candidates, env)
	}
	if defaultProjectRoot != "" {
		candidates = append(candidates, defaultProjectRoot)
	}
	if exe, err := os.Executable(); err == nil {
		dir := filepath.Dir(exe)
		candidates = append(candidates, dir, filepath.Dir(dir))
	}
	if wd, err := os.Getwd(); err == nil {
		for current := wd; ; current = filepath.Dir(current) {
			candidates = append(candidates, current)
			parent := filepath.Dir(current)
			if parent == current {
				break
			}
		}
	}

	for _, candidate := range candidates {
		root, err := filepath.Abs(candidate)
		if err != nil {
			continue
		}
		if fileExists(filepath.Join(root, "bin", "codexswitch")) &&
			fileExists(filepath.Join(root, "bin", "codexswitch-tui")) {
			return root, nil
		}
	}
	return "", errors.New("project root not found; set CODEXSWITCH_HOME to the codexswitch checkout")
}

func pythonBinary(root string) (string, error) {
	candidates := []string{}
	if runtime.GOOS == "windows" {
		candidates = append(candidates, filepath.Join(root, ".venv", "Scripts", "python.exe"), "python.exe", "py.exe")
	} else {
		candidates = append(candidates, filepath.Join(root, ".venv", "bin", "python"), "python3", "python")
	}
	for _, candidate := range candidates {
		if filepath.IsAbs(candidate) {
			if fileExists(candidate) {
				return candidate, nil
			}
			continue
		}
		if found, err := exec.LookPath(candidate); err == nil {
			return found, nil
		}
	}
	return "", errors.New("Python not found; create .venv or install Python")
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}
