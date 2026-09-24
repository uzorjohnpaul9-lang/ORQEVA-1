"""
AI Trading System - Main Entry Point
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_system import TradingSystem
from config.settings import trading_settings, monitoring_settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, monitoring_settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(monitoring_settings.log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point."""
    print("=" * 60)
    print("AI TRADING SYSTEM")
    print("=" * 60)
    print(f"Risk Profile: {trading_settings.default_risk_profile}")
    print(f"Trading Enabled: {trading_settings.trading_enabled}")
    print("=" * 60)
    
    # Initialize trading system
    system = TradingSystem(trading_settings.default_risk_profile)
    
    try:
        # Start the system
        system.start()
        print("\nSystem started successfully!")
        print(f"Portfolio Value: ${system.paper_trader.get_portfolio_value():,.2f}")
        print(f"Risk Profile: {system.risk_profile.name}")
        print(f"Max Risk Per Trade: {system.risk_profile.risk_per_trade:.1%}")
        print(f"Max Daily Loss: {system.risk_profile.max_daily_loss:.1%}")
        print(f"Max Positions: {system.risk_profile.max_positions}")
        
        # Demo: Analyze a symbol
        print("\n" + "=" * 60)
        print("DEMO: Analyzing AAPL")
        print("=" * 60)
        
        analysis = system.analyze_symbol("AAPL")
        print(f"Current Price: ${analysis.get('current_price', 0):.2f}")
        print(f"Market Regime: {analysis.get('regime', {}).get('regime', 'unknown')}")
        print(f"RSI: {analysis.get('indicators', {}).get('rsi', 'N/A')}")
        
        if analysis.get('entry_signal'):
            print(f"\nEntry Signal: {analysis['entry_signal'].get('direction', 'none')}")
            print(f"Confidence: {analysis['confidence'].get('confidence', 0):.2%}")
        
        # Demo: Execute a paper trade
        print("\n" + "=" * 60)
        print("DEMO: Executing Paper Trade")
        print("=" * 60)
        
        trade_result = system.execute_paper_trade(
            symbol="AAPL",
            quantity=10,
            side="buy"
        )
        
        if "error" in trade_result:
            print(f"Trade Error: {trade_result['error']}")
            if "reasons" in trade_result:
                for reason in trade_result["reasons"]:
                    print(f"  - {reason}")
        else:
            print(f"Order ID: {trade_result.get('id')}")
            print(f"Status: {trade_result.get('status')}")
            print(f"Filled Price: ${trade_result.get('filled_price', 0):.2f}")
        
        # Show portfolio status
        print("\n" + "=" * 60)
        print("PORTFOLIO STATUS")
        print("=" * 60)
        
        status = system.get_portfolio_status()
        print(f"Portfolio Value: ${status['portfolio_value']:,.2f}")
        print(f"Available Capital: ${status['capital']:,.2f}")
        print(f"Open Positions: {len(status['positions'])}")
        
        print("\nSystem is running. Press Ctrl+C to stop.")
        while True:
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        system.stop()
        print("\nSystem stopped.")
    except Exception as e:
        logger.error(f"System error: {e}")
        system.stop()
        print(f"\nSystem error: {e}")

if __name__ == "__main__":
    main()
