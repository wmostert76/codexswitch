package main

import (
	"log"
	"os"

	"github.com/wmostert76/codexswitch/internal/proxy"
)

func main() {
	logger := log.New(os.Stdout, "codexswitch-proxy: ", log.LstdFlags)
	if err := proxy.Run(logger); err != nil {
		logger.Fatal(err)
	}
}
