"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    NEXUS AI - Security Audit Module                           ║
║          Automated smart contract vulnerability detection                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime
from pathlib import Path
from loguru import logger


class Severity(Enum):
    """Vulnerability severity levels"""
    CRITICAL = "critical"  # Immediate fund loss risk
    HIGH = "high"          # Significant risk
    MEDIUM = "medium"      # Moderate risk
    LOW = "low"            # Minor issues
    INFO = "info"          # Informational


class VulnerabilityType(Enum):
    """Known vulnerability types"""
    REENTRANCY = "reentrancy"
    OVERFLOW = "overflow"
    UNDERFLOW = "underflow"
    ACCESS_CONTROL = "access_control"
    FRONT_RUNNING = "front_running"
    ORACLE_MANIPULATION = "oracle_manipulation"
    FLASH_LOAN = "flash_loan"
    TIMESTAMP_DEPENDENCE = "timestamp_dependence"
    TX_ORIGIN = "tx_origin"
    UNCHECKED_RETURN = "unchecked_return"
    DOS = "denial_of_service"
    CENTRALIZATION = "centralization"
    RUGPULL = "rugpull"
    HONEYPOT = "honeypot"
    UNINITIALIZED_STORAGE = "uninitialized_storage"
    DELEGATE_CALL = "delegate_call"
    SELFDESTRUCT = "selfdestruct"
    ARBITRARY_SEND = "arbitrary_send"
    SIGNATURE_REPLAY = "signature_replay"


@dataclass
class Vulnerability:
    """Detected vulnerability"""
    id: str
    type: VulnerabilityType
    severity: Severity
    title: str
    description: str
    location: str  # file:line
    code_snippet: str
    recommendation: str
    confidence: float  # 0-1
    references: List[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """Complete audit result"""
    contract_name: str
    contract_address: Optional[str]
    audit_time: datetime
    vulnerabilities: List[Vulnerability]
    risk_score: float  # 0-100
    is_safe: bool
    summary: str
    gas_issues: List[Dict[str, Any]] = field(default_factory=list)
    code_quality: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PatternMatcher:
    """
    Pattern-based vulnerability detection
    """
    
    # Reentrancy patterns
    REENTRANCY_PATTERNS = [
        # External call before state change
        r'\.call\{[^}]*\}\([^)]*\).*\n.*=',
        r'\.transfer\([^)]*\).*\n.*=',
        r'\.send\([^)]*\).*\n.*=',
        # call without reentrancy guard
        r'(?<!nonReentrant).*\.call\{value:',
    ]
    
    # Access control issues
    ACCESS_CONTROL_PATTERNS = [
        r'function\s+\w+\s*\([^)]*\)\s+public(?!\s+onlyOwner)',
        r'function\s+\w+\s*\([^)]*\)\s+external(?!\s+onlyOwner)',
        r'selfdestruct\s*\(',
        r'delegatecall\s*\(',
    ]
    
    # tx.origin misuse
    TX_ORIGIN_PATTERNS = [
        r'tx\.origin',
        r'require\s*\([^)]*tx\.origin',
    ]
    
    # Timestamp dependence
    TIMESTAMP_PATTERNS = [
        r'block\.timestamp',
        r'now\s*[<>=]',
        r'block\.number\s*%',
    ]
    
    # Unchecked return values
    UNCHECKED_RETURN_PATTERNS = [
        r'\.transfer\s*\([^)]*\)\s*;',  # transfer without check
        r'\.call\s*\{[^}]*\}\s*\([^)]*\)\s*;',  # call without check
    ]
    
    # Centralization risks
    CENTRALIZATION_PATTERNS = [
        r'onlyOwner',
        r'Ownable',
        r'function\s+pause\s*\(',
        r'function\s+unpause\s*\(',
        r'function\s+blacklist\s*\(',
        r'function\s+setFee\s*\(',
        r'function\s+mint\s*\([^)]*\)\s+external',
    ]
    
    # Rugpull indicators
    RUGPULL_PATTERNS = [
        r'function\s+withdraw\w*\s*\([^)]*\)\s+external\s+onlyOwner',
        r'function\s+drain\w*\s*\(',
        r'_transfer\s*\([^)]*\).*blacklist',
        r'bool\s+public\s+tradingEnabled',
        r'function\s+enableTrading\s*\(',
        r'maxWallet.*onlyOwner',
        r'setMaxWallet.*onlyOwner',
    ]
    
    # Honeypot patterns
    HONEYPOT_PATTERNS = [
        r'require\s*\([^)]*_isExcluded',
        r'if\s*\(\s*!_isExcluded\[',
        r'mapping\s*\([^)]*\)\s*public\s+canSell',
        r'function\s+_transfer.*require.*from.*!=.*address',
    ]
    
    @classmethod
    def match_all(cls, code: str) -> Dict[str, List[tuple]]:
        """Match all patterns against code"""
        results = {}
        
        pattern_groups = {
            'reentrancy': cls.REENTRANCY_PATTERNS,
            'access_control': cls.ACCESS_CONTROL_PATTERNS,
            'tx_origin': cls.TX_ORIGIN_PATTERNS,
            'timestamp': cls.TIMESTAMP_PATTERNS,
            'unchecked_return': cls.UNCHECKED_RETURN_PATTERNS,
            'centralization': cls.CENTRALIZATION_PATTERNS,
            'rugpull': cls.RUGPULL_PATTERNS,
            'honeypot': cls.HONEYPOT_PATTERNS,
        }
        
        for group_name, patterns in pattern_groups.items():
            matches = []
            for pattern in patterns:
                try:
                    for match in re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE):
                        line_num = code[:match.start()].count('\n') + 1
                        matches.append((line_num, match.group(), pattern))
                except re.error:
                    continue
            if matches:
                results[group_name] = matches
        
        return results


class SecurityScanner:
    """
    Main security scanner for smart contracts
    """
    
    def __init__(self):
        self.pattern_matcher = PatternMatcher()
        self._vuln_counter = 0
    
    def scan_code(self, code: str, contract_name: str = "Unknown") -> AuditResult:
        """
        Scan Solidity code for vulnerabilities
        
        Args:
            code: Solidity source code
            contract_name: Name of the contract
            
        Returns:
            AuditResult with all findings
        """
        vulnerabilities = []
        self._vuln_counter = 0
        
        # Pattern matching
        matches = self.pattern_matcher.match_all(code)
        
        # Process matches into vulnerabilities
        for pattern_type, pattern_matches in matches.items():
            vulns = self._process_matches(pattern_type, pattern_matches, code)
            vulnerabilities.extend(vulns)
        
        # Additional semantic checks
        vulnerabilities.extend(self._check_modifiers(code))
        vulnerabilities.extend(self._check_visibility(code))
        vulnerabilities.extend(self._check_integer_safety(code))
        vulnerabilities.extend(self._check_external_calls(code))
        
        # Gas optimization issues
        gas_issues = self._check_gas_issues(code)
        
        # Code quality
        code_quality = self._analyze_code_quality(code)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(vulnerabilities)
        
        # Determine if safe
        is_safe = not any(v.severity in [Severity.CRITICAL, Severity.HIGH] for v in vulnerabilities)
        
        # Generate summary
        summary = self._generate_summary(vulnerabilities, risk_score)
        
        return AuditResult(
            contract_name=contract_name,
            contract_address=None,
            audit_time=datetime.now(),
            vulnerabilities=vulnerabilities,
            risk_score=risk_score,
            is_safe=is_safe,
            summary=summary,
            gas_issues=gas_issues,
            code_quality=code_quality
        )
    
    def _process_matches(
        self,
        pattern_type: str,
        matches: List[tuple],
        code: str
    ) -> List[Vulnerability]:
        """Convert pattern matches to vulnerabilities"""
        vulns = []
        
        type_map = {
            'reentrancy': (VulnerabilityType.REENTRANCY, Severity.CRITICAL),
            'access_control': (VulnerabilityType.ACCESS_CONTROL, Severity.HIGH),
            'tx_origin': (VulnerabilityType.TX_ORIGIN, Severity.HIGH),
            'timestamp': (VulnerabilityType.TIMESTAMP_DEPENDENCE, Severity.MEDIUM),
            'unchecked_return': (VulnerabilityType.UNCHECKED_RETURN, Severity.MEDIUM),
            'centralization': (VulnerabilityType.CENTRALIZATION, Severity.LOW),
            'rugpull': (VulnerabilityType.RUGPULL, Severity.CRITICAL),
            'honeypot': (VulnerabilityType.HONEYPOT, Severity.CRITICAL),
        }
        
        vuln_type, severity = type_map.get(pattern_type, (VulnerabilityType.ACCESS_CONTROL, Severity.LOW))
        
        recommendations = {
            'reentrancy': "Use ReentrancyGuard from OpenZeppelin or implement checks-effects-interactions pattern",
            'access_control': "Add proper access control modifiers (onlyOwner, onlyRole, etc.)",
            'tx_origin': "Replace tx.origin with msg.sender for authentication",
            'timestamp': "Avoid using block.timestamp for critical logic, use block.number or oracles",
            'unchecked_return': "Always check return values of external calls",
            'centralization': "Consider using multi-sig or DAO governance for critical functions",
            'rugpull': "This pattern is commonly associated with rugpull contracts - extreme caution",
            'honeypot': "Potential honeypot detected - users may not be able to sell tokens",
        }
        
        # Deduplicate by line number
        seen_lines: Set[int] = set()
        
        for line_num, matched_text, pattern in matches:
            if line_num in seen_lines:
                continue
            seen_lines.add(line_num)
            
            self._vuln_counter += 1
            
            # Get code snippet
            lines = code.split('\n')
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 2)
            snippet = '\n'.join(lines[start:end])
            
            vulns.append(Vulnerability(
                id=f"VULN-{self._vuln_counter:04d}",
                type=vuln_type,
                severity=severity,
                title=f"{pattern_type.replace('_', ' ').title()} Issue",
                description=f"Potential {pattern_type} vulnerability detected at line {line_num}",
                location=f"line:{line_num}",
                code_snippet=snippet,
                recommendation=recommendations.get(pattern_type, "Review and fix this issue"),
                confidence=0.7,
                references=[f"https://swcregistry.io/docs/SWC-{hash(pattern_type) % 200 + 100}"]
            ))
        
        return vulns
    
    def _check_modifiers(self, code: str) -> List[Vulnerability]:
        """Check for missing or improper modifiers"""
        vulns = []
        
        # Check for functions that modify state without modifiers
        func_pattern = r'function\s+(\w+)\s*\([^)]*\)\s+(public|external)\s*{'
        
        for match in re.finditer(func_pattern, code, re.MULTILINE):
            func_name = match.group(1)
            
            # Skip view/pure functions
            if 'view' in code[match.start():match.end()+100] or 'pure' in code[match.start():match.end()+100]:
                continue
            
            # Skip if has modifiers
            if 'onlyOwner' in code[match.start():match.end()+50] or 'onlyRole' in code[match.start():match.end()+50]:
                continue
            
            # Check if function modifies state (simplified)
            func_body_start = code.find('{', match.start())
            if func_body_start > 0:
                # Look for state modifications
                snippet = code[func_body_start:func_body_start+500]
                if '=' in snippet and 'require' not in snippet[:50]:
                    line_num = code[:match.start()].count('\n') + 1
                    self._vuln_counter += 1
                    
                    vulns.append(Vulnerability(
                        id=f"VULN-{self._vuln_counter:04d}",
                        type=VulnerabilityType.ACCESS_CONTROL,
                        severity=Severity.MEDIUM,
                        title=f"Missing Access Control on {func_name}",
                        description=f"Function {func_name} modifies state but has no access control",
                        location=f"line:{line_num}",
                        code_snippet=code[match.start():match.start()+200],
                        recommendation="Add appropriate access control modifier",
                        confidence=0.5
                    ))
        
        return vulns
    
    def _check_visibility(self, code: str) -> List[Vulnerability]:
        """Check for visibility issues"""
        vulns = []
        
        # Check for public state variables that should be private
        public_vars = re.findall(r'(\w+)\s+public\s+(\w+)\s*;', code)
        
        sensitive_patterns = ['password', 'secret', 'private', 'key', 'seed']
        
        for var_type, var_name in public_vars:
            if any(p in var_name.lower() for p in sensitive_patterns):
                self._vuln_counter += 1
                vulns.append(Vulnerability(
                    id=f"VULN-{self._vuln_counter:04d}",
                    type=VulnerabilityType.ACCESS_CONTROL,
                    severity=Severity.HIGH,
                    title=f"Sensitive Variable Publicly Visible: {var_name}",
                    description=f"Variable {var_name} appears to contain sensitive data but is public",
                    location="unknown",
                    code_snippet=f"{var_type} public {var_name};",
                    recommendation="Change visibility to private",
                    confidence=0.8
                ))
        
        return vulns
    
    def _check_integer_safety(self, code: str) -> List[Vulnerability]:
        """Check for integer overflow/underflow risks"""
        vulns = []
        
        # Check Solidity version for built-in overflow checks
        version_match = re.search(r'pragma\s+solidity\s+\^?(\d+)\.(\d+)', code)
        
        if version_match:
            major, minor = int(version_match.group(1)), int(version_match.group(2))
            
            # Before 0.8.0, no built-in overflow protection
            if major == 0 and minor < 8:
                # Check if SafeMath is used
                if 'SafeMath' not in code:
                    self._vuln_counter += 1
                    vulns.append(Vulnerability(
                        id=f"VULN-{self._vuln_counter:04d}",
                        type=VulnerabilityType.OVERFLOW,
                        severity=Severity.HIGH,
                        title="No Overflow Protection",
                        description=f"Solidity {major}.{minor} does not have built-in overflow protection and SafeMath is not used",
                        location="pragma statement",
                        code_snippet=f"pragma solidity ^{major}.{minor}",
                        recommendation="Upgrade to Solidity 0.8.0+ or use SafeMath library",
                        confidence=0.9
                    ))
        
        # Check for unchecked blocks in 0.8+
        unchecked_matches = re.finditer(r'unchecked\s*\{', code)
        for match in unchecked_matches:
            line_num = code[:match.start()].count('\n') + 1
            self._vuln_counter += 1
            vulns.append(Vulnerability(
                id=f"VULN-{self._vuln_counter:04d}",
                type=VulnerabilityType.OVERFLOW,
                severity=Severity.MEDIUM,
                title="Unchecked Math Block",
                description="Unchecked block disables overflow protection - ensure this is intentional",
                location=f"line:{line_num}",
                code_snippet=code[match.start():match.start()+100],
                recommendation="Only use unchecked for gas optimization when overflow is impossible",
                confidence=0.6
            ))
        
        return vulns
    
    def _check_external_calls(self, code: str) -> List[Vulnerability]:
        """Check for dangerous external call patterns"""
        vulns = []
        
        # Check for low-level calls
        call_patterns = [
            (r'\.call\s*\(', 'Low-level call detected'),
            (r'\.delegatecall\s*\(', 'Delegatecall detected - ensure target is trusted'),
            (r'\.staticcall\s*\(', 'Static call detected'),
            (r'assembly\s*\{', 'Inline assembly detected'),
        ]
        
        for pattern, description in call_patterns:
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                self._vuln_counter += 1
                
                severity = Severity.HIGH if 'delegatecall' in pattern else Severity.MEDIUM
                
                vulns.append(Vulnerability(
                    id=f"VULN-{self._vuln_counter:04d}",
                    type=VulnerabilityType.DELEGATE_CALL if 'delegatecall' in pattern else VulnerabilityType.UNCHECKED_RETURN,
                    severity=severity,
                    title=description,
                    description=f"{description} at line {line_num}. Low-level operations require careful handling.",
                    location=f"line:{line_num}",
                    code_snippet=code[match.start():match.start()+150],
                    recommendation="Ensure return values are checked and reentrancy protection is in place",
                    confidence=0.7
                ))
        
        return vulns
    
    def _check_gas_issues(self, code: str) -> List[Dict[str, Any]]:
        """Check for gas optimization opportunities"""
        issues = []
        
        # Check for storage in loops
        if re.search(r'for\s*\([^)]*\)\s*\{[^}]*\w+\s*\+=', code, re.DOTALL):
            issues.append({
                'type': 'storage_in_loop',
                'severity': 'medium',
                'description': 'Storage variable modified in loop - consider using memory variable'
            })
        
        # Check for public instead of external
        external_candidate = len(re.findall(r'function\s+\w+\s*\([^)]*\)\s+public\s+view', code))
        if external_candidate > 3:
            issues.append({
                'type': 'public_vs_external',
                'severity': 'low',
                'description': f'{external_candidate} public view functions could be external for gas savings'
            })
        
        # Check for multiple SLOADs
        if code.count('storage') > 10:
            issues.append({
                'type': 'excessive_sload',
                'severity': 'low',
                'description': 'Consider caching storage variables in memory'
            })
        
        return issues
    
    def _analyze_code_quality(self, code: str) -> Dict[str, Any]:
        """Analyze code quality metrics"""
        lines = code.split('\n')
        
        return {
            'total_lines': len(lines),
            'code_lines': len([l for l in lines if l.strip() and not l.strip().startswith('//')]),
            'comment_lines': len([l for l in lines if l.strip().startswith('//')]),
            'functions': len(re.findall(r'function\s+\w+', code)),
            'modifiers': len(re.findall(r'modifier\s+\w+', code)),
            'events': len(re.findall(r'event\s+\w+', code)),
            'imports': len(re.findall(r'import\s+', code)),
            'interfaces': len(re.findall(r'interface\s+\w+', code)),
            'uses_openzeppelin': 'openzeppelin' in code.lower(),
            'has_natspec': '@dev' in code or '@notice' in code,
        }
    
    def _calculate_risk_score(self, vulnerabilities: List[Vulnerability]) -> float:
        """Calculate overall risk score (0-100)"""
        if not vulnerabilities:
            return 0.0
        
        severity_weights = {
            Severity.CRITICAL: 40,
            Severity.HIGH: 25,
            Severity.MEDIUM: 15,
            Severity.LOW: 5,
            Severity.INFO: 1,
        }
        
        total_weight = 0
        for vuln in vulnerabilities:
            weight = severity_weights.get(vuln.severity, 0) * vuln.confidence
            total_weight += weight
        
        # Cap at 100
        return min(100.0, total_weight)
    
    def _generate_summary(self, vulnerabilities: List[Vulnerability], risk_score: float) -> str:
        """Generate audit summary"""
        if not vulnerabilities:
            return "No vulnerabilities detected. Contract appears to follow security best practices."
        
        severity_counts = {s: 0 for s in Severity}
        for v in vulnerabilities:
            severity_counts[v.severity] += 1
        
        parts = []
        if severity_counts[Severity.CRITICAL] > 0:
            parts.append(f"{severity_counts[Severity.CRITICAL]} CRITICAL")
        if severity_counts[Severity.HIGH] > 0:
            parts.append(f"{severity_counts[Severity.HIGH]} HIGH")
        if severity_counts[Severity.MEDIUM] > 0:
            parts.append(f"{severity_counts[Severity.MEDIUM]} MEDIUM")
        if severity_counts[Severity.LOW] > 0:
            parts.append(f"{severity_counts[Severity.LOW]} LOW")
        
        risk_level = "LOW" if risk_score < 25 else "MEDIUM" if risk_score < 50 else "HIGH" if risk_score < 75 else "CRITICAL"
        
        return f"Found {len(vulnerabilities)} issues ({', '.join(parts)}). Risk Level: {risk_level} ({risk_score:.1f}/100)"
    
    def generate_report(self, result: AuditResult) -> str:
        """Generate detailed text report"""
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       NEXUS AI SECURITY AUDIT REPORT                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 CONTRACT INFORMATION
────────────────────────────────────────────────────────────────────────
Contract:        {result.contract_name}
Address:         {result.contract_address or 'N/A'}
Audit Date:      {result.audit_time.strftime('%Y-%m-%d %H:%M:%S')}
Risk Score:      {result.risk_score:.1f}/100
Status:          {'✅ SAFE' if result.is_safe else '⚠️ ISSUES FOUND'}

📊 SUMMARY
────────────────────────────────────────────────────────────────────────
{result.summary}

"""
        
        if result.vulnerabilities:
            report += """
🔴 VULNERABILITIES
────────────────────────────────────────────────────────────────────────
"""
            for vuln in sorted(result.vulnerabilities, key=lambda v: list(Severity).index(v.severity)):
                severity_icon = {
                    Severity.CRITICAL: "🔴",
                    Severity.HIGH: "🟠",
                    Severity.MEDIUM: "🟡",
                    Severity.LOW: "🟢",
                    Severity.INFO: "🔵",
                }.get(vuln.severity, "⚪")
                
                report += f"""
{severity_icon} [{vuln.severity.value.upper()}] {vuln.title}
   ID: {vuln.id}
   Location: {vuln.location}
   Confidence: {vuln.confidence:.0%}
   
   Description:
   {vuln.description}
   
   Code:
   ```
{vuln.code_snippet}
   ```
   
   Recommendation:
   {vuln.recommendation}

"""
        
        if result.gas_issues:
            report += """
⛽ GAS OPTIMIZATION OPPORTUNITIES
────────────────────────────────────────────────────────────────────────
"""
            for issue in result.gas_issues:
                report += f"  • [{issue['severity'].upper()}] {issue['description']}\n"
        
        if result.code_quality:
            cq = result.code_quality
            report += f"""
📈 CODE QUALITY METRICS
────────────────────────────────────────────────────────────────────────
  Total Lines:       {cq.get('total_lines', 0)}
  Code Lines:        {cq.get('code_lines', 0)}
  Comment Lines:     {cq.get('comment_lines', 0)}
  Functions:         {cq.get('functions', 0)}
  Modifiers:         {cq.get('modifiers', 0)}
  Events:            {cq.get('events', 0)}
  Uses OpenZeppelin: {'Yes' if cq.get('uses_openzeppelin') else 'No'}
  Has NatSpec:       {'Yes' if cq.get('has_natspec') else 'No'}
"""
        
        report += """
══════════════════════════════════════════════════════════════════════════════
                         End of Security Audit Report
══════════════════════════════════════════════════════════════════════════════
"""
        return report


class TokenSecurityChecker:
    """
    Specialized checker for ERC20/token contracts
    """
    
    RUGPULL_INDICATORS = [
        ('hidden_owner', r'function\s+\w*owner\w*\s*\([^)]*\)\s+private'),
        ('hidden_mint', r'function\s+_\w*mint\w*\s*\([^)]*\)\s+internal'),
        ('fee_manipulation', r'function\s+set\w*Fee\s*\([^)]*\)\s+\w+\s+onlyOwner'),
        ('blacklist', r'mapping\s*\([^)]*\)\s+\w+\s+\w*blacklist'),
        ('pause_trading', r'bool\s+\w+\s+tradingEnabled'),
        ('max_tx_manipulation', r'function\s+setMaxTx'),
        ('hidden_transfer_fee', r'_transfer.*amount\s*\*'),
        ('can_disable_selling', r'function\s+\w*sell\w*\s*\([^)]*bool'),
    ]
    
    def check_token_safety(self, code: str) -> Dict[str, Any]:
        """Check token contract for rugpull indicators"""
        results = {
            'is_safe': True,
            'risk_level': 'low',
            'indicators': [],
            'warnings': []
        }
        
        indicator_count = 0
        
        for name, pattern in self.RUGPULL_INDICATORS:
            if re.search(pattern, code, re.IGNORECASE):
                indicator_count += 1
                results['indicators'].append({
                    'name': name,
                    'found': True,
                    'severity': 'high' if name in ['hidden_mint', 'can_disable_selling'] else 'medium'
                })
        
        # Determine risk level
        if indicator_count >= 3:
            results['is_safe'] = False
            results['risk_level'] = 'critical'
            results['warnings'].append("Multiple rugpull indicators detected!")
        elif indicator_count >= 2:
            results['is_safe'] = False
            results['risk_level'] = 'high'
            results['warnings'].append("Potential rugpull risk - proceed with caution")
        elif indicator_count >= 1:
            results['risk_level'] = 'medium'
            results['warnings'].append("Some concerning patterns detected")
        
        return results


# Global scanner instance
security_scanner = SecurityScanner()
token_checker = TokenSecurityChecker()


async def quick_scan(code: str, contract_name: str = "Unknown") -> AuditResult:
    """Quick security scan"""
    return security_scanner.scan_code(code, contract_name)


async def full_audit(code: str, contract_name: str = "Unknown") -> str:
    """Full audit with report"""
    result = security_scanner.scan_code(code, contract_name)
    return security_scanner.generate_report(result)
