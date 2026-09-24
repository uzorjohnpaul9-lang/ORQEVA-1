"""
AI Trading System - Demo Script
Run this to test the system functionality.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_system import TradingSystem

def run_demo():
    """Run a complete demo of the trading system."""
    
    print("=" * 70)
    print("AI TRADING SYSTEM - COMPLETE DEMO")
    print("=" * 70)
    
    # Initialize system
    print("\n[1] Initializing Trading System...")
    system = TradingSystem("conservative")
    system.start()
    print("    [OK] System started with Conservative risk profile")
    
    # Show initial status
    print("\n[2] Initial Portfolio Status:")
    status = system.get_portfolio_status()
    print(f"    Portfolio Value: ${status['portfolio_value']:,.2f}")
    print(f"    Available Capital: ${status['capital']:,.2f}")
    print(f"    Risk Profile: {status['risk_profile']}")
    
    # Analyze symbols
    print("\n[3] Analyzing Market Symbols...")
    symbols = ["AAPL", "MSFT", "GOOGL"]
    
    for symbol in symbols:
        print(f"\n    Analyzing {symbol}...")
        analysis = system.analyze_symbol(symbol)
        
        if "error" not in analysis:
            print(f"    [OK] Price: ${analysis.get('current_price', 0):.2f}")
            print(f"    [OK] Regime: {analysis.get('regime', {}).get('regime', 'unknown')}")
            rsi_val = analysis.get('indicators', {}).get('rsi', None)
            if rsi_val is not None:
                print(f"    [OK] RSI: {rsi_val:.2f}")
            else:
                print(f"    [OK] RSI: N/A")
            
            if analysis.get('entry_signal'):
                print(f"    [OK] Signal: {analysis['entry_signal'].get('direction', 'none')}")
                print(f"    [OK] Confidence: {analysis['confidence'].get('confidence', 0):.2%}")
        else:
            print(f"    [ERR] Error: {analysis['error']}")
    
    # Execute trades
    print("\n[4] Executing Paper Trades...")
    
    trades = [
        {"symbol": "AAPL", "quantity": 5, "side": "buy"},
        {"symbol": "MSFT", "quantity": 3, "side": "buy"},
    ]
    
    for trade in trades:
        print(f"\n    Trading {trade['side'].upper()} {trade['quantity']} {trade['symbol']}...")
        result = system.execute_paper_trade(**trade)
        
        if "error" in result:
            print(f"    [ERR] Error: {result['error']}")
            if "reasons" in result:
                for reason in result["reasons"]:
                    print(f"      - {reason}")
        else:
            print(f"    [OK] Order ID: {result.get('id')}")
            print(f"    [OK] Status: {result.get('status')}")
            print(f"    [OK] Filled Price: ${result.get('filled_price', 0):.2f}")
    
    # Final status
    print("\n[5] Final Portfolio Status:")
    final_status = system.get_portfolio_status()
    print(f"    Portfolio Value: ${final_status['portfolio_value']:,.2f}")
    print(f"    Available Capital: ${final_status['capital']:,.2f}")
    print(f"    Open Positions: {len(final_status['positions'])}")
    
    if final_status['positions']:
        print("\n    Open Positions:")
        for symbol, pos in final_status['positions'].items():
            print(f"      {symbol}: {pos['quantity']} shares @ ${pos['avg_price']:.2f}")
    
    # Test kill switch
    print("\n[6] Testing Kill Switch...")
    system.activate_kill_switch("Demo test")
    print(f"    Kill Switch Active: {system.kill_switch.is_active}")
    
    # Try to trade with kill switch active
    print("    Attempting trade with kill switch active...")
    result = system.execute_paper_trade("AAPL", 1, "buy")
    if "error" in result:
        print(f"    [OK] Trade correctly rejected: {result['error']}")
    
    system.deactivate_kill_switch()
    print(f"    Kill Switch Deactivated: {not system.kill_switch.is_active}")
    
    # Stop system
    print("\n[7] Stopping System...")
    system.stop()
    print("    [OK] System stopped successfully")
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
