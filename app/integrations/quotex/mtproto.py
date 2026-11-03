import asyncio
import logging
import time
from typing import Optional, Dict, Any, Set
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from app.config import settings
from app.database.models import VerificationStatus
from app.integrations.quotex.base import QuotexVerificationProvider, TraderVerificationResult
from app.integrations.quotex.parser import QuotexPartnerResponseParser, ParsedQuotexTraderData

logger = logging.getLogger(__name__)


class PartnerBotMTProtoProvider(QuotexVerificationProvider):
    """Automated Quotex verification provider using Telegram MTProto user client.

    Sends '/TRADER_ID' to @QuotexPartnerBot, awaits and parses the incoming response,
    and returns verified telemetry.
    """

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_string: Optional[str] = None,
        partner_bot_username: str = "QuotexPartnerBot",
        timeout_seconds: int = 20,
        rate_limit_delay: float = 2.0
    ):
        self.api_id = api_id or getattr(settings, "TELEGRAM_API_ID", None)
        self.api_hash = api_hash or getattr(settings, "TELEGRAM_API_HASH", None)
        self.session_string = session_string or getattr(settings, "TELEGRAM_SESSION_STRING", None)
        self.partner_bot_username = partner_bot_username
        self.timeout_seconds = timeout_seconds
        self.rate_limit_delay = rate_limit_delay

        self._client: Optional[TelegramClient] = None
        self._lock = asyncio.Lock()
        self._last_query_time: float = 0.0
        self._in_flight_traders: Set[str] = set()

    @property
    def is_configured(self) -> bool:
        """Check if MTProto credentials are configured."""
        return bool(self.api_id and self.api_hash and self.session_string)

    async def get_client(self) -> Optional[TelegramClient]:
        """Lazy-initialize and connect Telethon client."""
        if not self.is_configured:
            return None

        if self._client is None or not self._client.is_connected():
            session = StringSession(self.session_string)
            self._client = TelegramClient(session, self.api_id, self.api_hash)
            await self._client.connect()
            if not await self._client.is_user_authorized():
                logger.error("MTProto session is not authorized. Please re-authenticate.")
                return None
            logger.info("Telethon MTProto client connected and authorized.")

        return self._client

    async def close(self) -> None:
        """Disconnect MTProto client cleanly."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            self._client = None

    async def verify_trader(
        self,
        trader_id: str,
        minimum_deposit: float = 100.0,
        expected_affiliate_id: str = "2414647"
    ) -> TraderVerificationResult:
        trader_id_clean = str(trader_id).strip()

        # Prevent duplicate simultaneous queries for the same trader
        if trader_id_clean in self._in_flight_traders:
            return TraderVerificationResult(
                trader_id=trader_id_clean,
                status=VerificationStatus.RETRY_PENDING,
                message="Verification check already in progress for this Trader ID. Please wait."
            )

        if not self.is_configured:
            logger.warning("MTProto provider queried but credentials are not configured.")
            return TraderVerificationResult(
                trader_id=trader_id_clean,
                status=VerificationStatus.RETRY_PENDING,
                message="Automated verification client not configured. Queued for retry / manual check."
            )

        client = await self.get_client()
        if not client:
            return TraderVerificationResult(
                trader_id=trader_id_clean,
                status=VerificationStatus.RETRY_PENDING,
                message="Could not establish MTProto connection to @QuotexPartnerBot."
            )

        self._in_flight_traders.add(trader_id_clean)
        try:
            async with self._lock:
                # Rate limit pacing
                elapsed = time.time() - self._last_query_time
                if elapsed < self.rate_limit_delay:
                    await asyncio.sleep(self.rate_limit_delay - elapsed)

                return await self._execute_partner_bot_query(
                    client=client,
                    trader_id=trader_id_clean,
                    minimum_deposit=minimum_deposit,
                    expected_affiliate_id=expected_affiliate_id
                )
        finally:
            self._in_flight_traders.discard(trader_id_clean)

    async def _execute_partner_bot_query(
        self,
        client: TelegramClient,
        trader_id: str,
        minimum_deposit: float,
        expected_affiliate_id: str
    ) -> TraderVerificationResult:
        response_future = asyncio.get_running_loop().create_future()

        # Event handler for incoming message from partner bot
        async def response_handler(event):
            sender = await event.get_sender()
            sender_username = getattr(sender, "username", "") or ""
            if sender_username.lower() == self.partner_bot_username.lower():
                text = event.raw_text or ""
                # Check correlation: either mentions trader id or an error message
                if trader_id in text or "not found" in text.lower() or "invalid" in text.lower():
                    if not response_future.done():
                        response_future.set_result(text)

        client.add_event_handler(response_handler, events.NewMessage(incoming=True))
        self._last_query_time = time.time()

        try:
            # Send /TRADER_ID to @QuotexPartnerBot
            command = f"/{trader_id}"
            await client.send_message(self.partner_bot_username, command)
            logger.info(f"Dispatched query '{command}' to @{self.partner_bot_username}")

            # Await response with timeout
            raw_response = await asyncio.wait_for(response_future, timeout=self.timeout_seconds)
            logger.info(f"Received response from @{self.partner_bot_username} for Trader #{trader_id}")

            return self._evaluate_parsed_response(
                raw_response=raw_response,
                requested_trader_id=trader_id,
                minimum_deposit=minimum_deposit,
                expected_affiliate_id=expected_affiliate_id
            )

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for @{self.partner_bot_username} response for Trader #{trader_id}")
            return TraderVerificationResult(
                trader_id=trader_id,
                status=VerificationStatus.RETRY_PENDING,
                message=f"Timeout waiting for response from @{self.partner_bot_username} ({self.timeout_seconds}s). Queued for retry."
            )
        except Exception as e:
            logger.error(f"Error querying @{self.partner_bot_username}: {e}", exc_info=True)
            return TraderVerificationResult(
                trader_id=trader_id,
                status=VerificationStatus.RETRY_PENDING,
                message=f"Partner Bot communication error: {e}"
            )
        finally:
            client.remove_event_handler(response_handler)

    def _evaluate_parsed_response(
        self,
        raw_response: str,
        requested_trader_id: str,
        minimum_deposit: float,
        expected_affiliate_id: str
    ) -> TraderVerificationResult:
        parsed = QuotexPartnerResponseParser.parse(raw_response)

        # 1. Not found
        if parsed.is_not_found:
            return TraderVerificationResult(
                trader_id=requested_trader_id,
                status=VerificationStatus.NOT_FOUND,
                raw_data={"raw_text": raw_response},
                message=f"Trader #{requested_trader_id} was not found in Quotex partner records."
            )

        # 2. Trader ID mismatch
        if parsed.trader_id and parsed.trader_id != requested_trader_id:
            logger.error(f"Trader ID mismatch! Requested: {requested_trader_id}, Received: {parsed.trader_id}")
            return TraderVerificationResult(
                trader_id=requested_trader_id,
                status=VerificationStatus.MANUAL_REVIEW,
                raw_data=parsed.model_dump(),
                message=f"Trader ID correlation mismatch (expected {requested_trader_id}, received {parsed.trader_id}). Marked for manual review."
            )

        # 3. Check Affiliate Link ID
        is_affiliate_matched = str(parsed.link_id).strip() == str(expected_affiliate_id).strip()
        if not is_affiliate_matched:
            return TraderVerificationResult(
                trader_id=requested_trader_id,
                status=VerificationStatus.WRONG_AFFILIATE,
                affiliate_link_id=parsed.link_id,
                deposit_amount=parsed.deposits_sum,
                is_affiliate_matched=False,
                is_deposit_sufficient=parsed.deposits_sum >= minimum_deposit,
                raw_data=parsed.model_dump(),
                message=f"Trader is registered under Link ID '{parsed.link_id}', expected '{expected_affiliate_id}'."
            )

        # 4. Check Deposit Amount
        is_deposit_sufficient = parsed.deposits_sum >= minimum_deposit
        if not is_deposit_sufficient:
            return TraderVerificationResult(
                trader_id=requested_trader_id,
                status=VerificationStatus.DEPOSIT_REQUIRED,
                affiliate_link_id=parsed.link_id,
                deposit_amount=parsed.deposits_sum,
                is_affiliate_matched=True,
                is_deposit_sufficient=False,
                raw_data=parsed.model_dump(),
                message=f"Affiliated with Link ID {expected_affiliate_id}. Verified deposit of ${parsed.deposits_sum:.2f} is below minimum requirement of ${minimum_deposit:.2f}."
            )

        # 5. Fully Verified
        return TraderVerificationResult(
            trader_id=requested_trader_id,
            status=VerificationStatus.VERIFIED,
            affiliate_link_id=parsed.link_id,
            deposit_amount=parsed.deposits_sum,
            is_affiliate_matched=True,
            is_deposit_sufficient=True,
            raw_data=parsed.model_dump(),
            message=f"Successfully verified! Affiliate Link ID {parsed.link_id} and deposit ${parsed.deposits_sum:.2f} meet requirement (${minimum_deposit:.2f})."
        )

    async def get_trader_details(self, trader_id: str) -> Optional[Dict[str, Any]]:
        res = await self.verify_trader(trader_id)
        return res.raw_data

    async def get_affiliate_link_id(self, trader_id: str) -> Optional[str]:
        res = await self.verify_trader(trader_id)
        return res.affiliate_link_id

    async def get_deposit_amount(self, trader_id: str) -> Optional[float]:
        res = await self.verify_trader(trader_id)
        return res.deposit_amount
