#!/bin/bash

# Agent Registration Script for OpenCode Sessions
# This script registers the current agent with puente daemon

set -euo pipefail

# Configuration
PUENTE_PORT_FILE="port"
DEFAULT_PUENTE_PORT="19842"
AGENT_COLOR=""
OPENCODE_PORT=""
SILENT_MODE=false
LOG_FILE="/tmp/agent-register-$(whoami).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_to_file() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log_info() {
    log_to_file "[INFO] $1"
    if [[ "$SILENT_MODE" != "true" ]]; then
        echo -e "${BLUE}[INFO]${NC} $1" >&2
    fi
}

log_success() {
    log_to_file "[SUCCESS] $1"
    if [[ "$SILENT_MODE" != "true" ]]; then
        echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
    fi
}

log_warning() {
    log_to_file "[WARNING] $1"
    if [[ "$SILENT_MODE" != "true" ]]; then
        echo -e "${YELLOW}[WARNING]${NC} $1" >&2
    fi
}

log_error() {
    log_to_file "[ERROR] $1"
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Register this OpenCode agent session with puente daemon"
    echo ""
    echo "Options:"
    echo "  -c, --color COLOR     Agent color (red, blue, green, black)"
    echo "  -p, --port PORT       OpenCode port (auto-detected if not provided)"
    echo "  -s, --silent          Silent mode (minimal output)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --color red                    # Auto-detect OpenCode port"
    echo "  $0 --color blue --port 44818      # Specify port manually"
    echo "  $0 --color red --silent           # Silent registration"
    echo ""
    echo "The script will:"
    echo "  1. Detect or use the provided OpenCode port"
    echo "  2. Find the puente daemon port"
    echo "  3. Register this agent with puente"
    echo "  4. Verify the registration succeeded"
}

detect_agent_color() {
    # Try to detect agent color from current directory or environment
    local pwd_name=$(basename "$PWD")
    
    case "$pwd_name" in
        *red*) echo "red" ;;
        *blue*) echo "blue" ;;
        *green*) echo "green" ;;
        *black*) echo "black" ;;
        *) echo "" ;;
    esac
}

detect_opencode_port() {
    # Method 1: Use parent process ID (current session)
    local opencode_pid=$PPID
    log_info "Checking parent process: $opencode_pid"
    
    # Find the port this OpenCode instance is listening on
    local port=$(netstat -tulnp 2>/dev/null | grep "$opencode_pid/opencode" | awk '{print $4}' | cut -d: -f2 | head -1)
    
    if [[ -n "$port" ]]; then
        echo "$port"
        return 0
    fi
    
    # Method 2: Look for any OpenCode process and try to match
    log_warning "Could not detect port from parent process, trying alternative methods..."
    
    # Get all OpenCode processes
    local opencode_pids=$(pgrep -f "opencode" 2>/dev/null || true)
    
    if [[ -n "$opencode_pids" ]]; then
        log_info "Found OpenCode processes: $opencode_pids"
        
        # Try each PID to find a listening port
        for pid in $opencode_pids; do
            local port=$(netstat -tulnp 2>/dev/null | grep "$pid/opencode" | awk '{print $4}' | cut -d: -f2 | head -1)
            if [[ -n "$port" ]]; then
                log_warning "Using port $port from OpenCode process $pid"
                echo "$port"
                return 0
            fi
        done
    fi
    
    # Method 3: Check common OpenCode ports
    log_warning "Trying common OpenCode ports..."
    for port in 44817 44818 44819 44820; do
        if curl -s "http://localhost:$port/health" >/dev/null 2>&1; then
            log_warning "Found OpenCode on port $port"
            echo "$port"
            return 0
        fi
    done
    
    log_error "Could not auto-detect OpenCode port"
    return 1
}

get_puente_port() {
    for port_file in "$PUENTE_PORT_FILE" "../$PUENTE_PORT_FILE"; do
        if [[ -f "$port_file" ]]; then
            local port=$(cat "$port_file" 2>/dev/null | tr -d '\n\r')
            if [[ -n "$port" && "$port" =~ ^[0-9]+$ ]]; then
                if curl -s "http://localhost:$port/health" >/dev/null 2>&1; then
                    log_info "Found puente port $port in file: $port_file"
                    echo "$port"
                    return 0
                else
                    log_warning "Port file $port_file shows $port but puente not responding there"
                fi
            fi
        fi
    done
    
    log_error "Could not find puente daemon"
    log_info "Please ensure puente is running with: python3 puente.py"
    return 1
}

register_agent() {
    local agent_color="$1"
    local opencode_port="$2"
    local puente_port="$3"
    
    log_info "Registering $agent_color agent (OpenCode port: $opencode_port) with puente (port: $puente_port)..."
    log_to_file "REGISTRATION_ATTEMPT: agent=$agent_color, opencode_port=$opencode_port, puente_port=$puente_port"
    
    local response=$(curl -s -X POST "http://localhost:$puente_port/register_agent" \
        -H "Content-Type: application/json" \
        -d "{\"agent_color\":\"$agent_color\",\"opencode_port\":$opencode_port}" \
        2>/dev/null)
    
    local curl_exit_code=$?
    log_to_file "CURL_RESPONSE: exit_code=$curl_exit_code, response_length=${#response}"
    
    if [[ $curl_exit_code -eq 0 && -n "$response" ]]; then
        log_to_file "RAW_RESPONSE: $response"
        local success=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('success', False))" 2>/dev/null)
        
        if [[ "$success" == "True" ]]; then
            log_to_file "REGISTRATION_SUCCESS: agent=$agent_color registered successfully"
            if [[ "$SILENT_MODE" == "true" ]]; then
                # Log to file only, no echo
                # Send toast notification to OpenCode (use /notify endpoint which may exist)
                curl -s -X POST "http://localhost:$opencode_port/notify" \
                    -H "Content-Type: application/json" \
                    -d "{\"message\":\"✅ Agent $agent_color registered successfully\",\"type\":\"success\"}" \
                    >/dev/null 2>&1 || \
                curl -s -X POST "http://localhost:$opencode_port/api/toast" \
                    -H "Content-Type: application/json" \
                    -d "{\"message\":\"✅ Agent $agent_color registered successfully\",\"type\":\"success\"}" \
                    >/dev/null 2>&1 || true
            else
                log_success "Agent $agent_color registered successfully!"
                                
                log_info "You will now receive brief notifications for new Slack messages"
            fi
            echo # Add proper newline
            return 0
        else
            local error_msg=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('error', 'Unknown error'))" 2>/dev/null)
            log_to_file "REGISTRATION_FAILED: error=$error_msg"
            log_error "Registration failed: $error_msg"
            # Send toast notification for failure
            curl -s -X POST "http://localhost:$opencode_port/notify" \
                -H "Content-Type: application/json" \
                -d "{\"message\":\"❌ Agent $agent_color registration failed: $error_msg\",\"type\":\"error\"}" \
                >/dev/null 2>&1 || \
            curl -s -X POST "http://localhost:$opencode_port/api/toast" \
                -H "Content-Type: application/json" \
                -d "{\"message\":\"❌ Agent $agent_color registration failed: $error_msg\",\"type\":\"error\"}" \
                >/dev/null 2>&1 || true
            echo # Add proper newline
            return 1
        fi
    else
        log_to_file "COMMUNICATION_FAILED: curl_exit_code=$curl_exit_code, response_empty=${#response}"
        log_error "Failed to communicate with puente daemon"
        # Send toast notification for communication failure
        curl -s -X POST "http://localhost:$opencode_port/notify" \
            -H "Content-Type: application/json" \
            -d "{\"message\":\"❌ Agent $agent_color registration failed: Cannot communicate with puente\",\"type\":\"error\"}" \
            >/dev/null 2>&1 || \
        curl -s -X POST "http://localhost:$opencode_port/api/toast" \
            -H "Content-Type: application/json" \
            -d "{\"message\":\"❌ Agent $agent_color registration failed: Cannot communicate with puente\",\"type\":\"error\"}" \
            >/dev/null 2>&1 || true
        echo # Add proper newline
        return 1
    fi
}

verify_registration() {
    local puente_port="$1"
    
    if [[ "$SILENT_MODE" == "true" ]]; then
        return 0
    fi
    
    log_info "Verifying registration..."
    
    local response=$(curl -s "http://localhost:$puente_port/list_agents" 2>/dev/null)
    
    if [[ $? -eq 0 && -n "$response" ]]; then
        if [[ "$SILENT_MODE" != "true" ]]; then
            log_info "Registration verified successfully"
        fi
        return 0
    else
        log_warning "Could not verify registration"
        return 1
    fi
}

main() {
    # If no arguments provided, enable silent mode for auto-registration
    if [[ $# -eq 0 ]]; then
        SILENT_MODE=true
    fi
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--color)
                AGENT_COLOR="$2"
                shift 2
                ;;
            -p|--port)
                OPENCODE_PORT="$2"
                shift 2
                ;;
            -s|--silent)
                SILENT_MODE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Auto-detect agent color if not provided
    if [[ -z "$AGENT_COLOR" ]]; then
        AGENT_COLOR=$(detect_agent_color)
        if [[ -n "$AGENT_COLOR" ]]; then
            log_info "Auto-detected agent color: $AGENT_COLOR"
        fi
    fi
    
    # Validate agent color
    if [[ -z "$AGENT_COLOR" ]]; then
        log_error "Agent color is required. Use --color or ensure directory name contains agent color."
        usage
        exit 1
    fi
    
    case "$AGENT_COLOR" in
        red|blue|green|black)
            ;;
        *)
            log_error "Invalid agent color: $AGENT_COLOR (must be: red, blue, green, black)"
            exit 1
            ;;
    esac
    
    # Auto-detect OpenCode port if not provided
    if [[ -z "$OPENCODE_PORT" ]]; then
        log_info "Auto-detecting OpenCode port..."
        OPENCODE_PORT=$(detect_opencode_port)
        if [[ $? -ne 0 ]]; then
            log_error "Please specify OpenCode port with --port"
            exit 1
        fi
        log_info "Detected OpenCode port: $OPENCODE_PORT"
    fi
    
    # Validate OpenCode port
    if ! [[ "$OPENCODE_PORT" =~ ^[0-9]+$ ]]; then
        log_error "Invalid OpenCode port: $OPENCODE_PORT"
        exit 1
    fi
    
    # Find puente daemon
    log_info "Looking for puente daemon..."
    local puente_port=$(get_puente_port)
    if [[ $? -ne 0 ]]; then
        log_error "Please ensure puente daemon is running"
        exit 1
    fi
    log_info "Found puente daemon on port: $puente_port"
    
    # Register agent
    if register_agent "$AGENT_COLOR" "$OPENCODE_PORT" "$puente_port"; then
        if [[ "$SILENT_MODE" != "true" ]]; then
            echo ""
            verify_registration "$puente_port"
            echo ""
            log_success "Registration complete! This agent will now receive Slack notifications."
        fi
    else
        exit 1
    fi
}

# Run main function
main "$@"
