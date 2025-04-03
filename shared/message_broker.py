import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable
from abc import ABC, abstractmethod

class MessageBroker(ABC):
    """Abstract base class for message brokers"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the message broker"""
        pass
    
    @abstractmethod
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """
        Publish a message to a topic
        
        Args:
            topic (str): Topic to publish to
            message (Dict[str, Any]): Message to publish
        """
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Subscribe to a topic
        
        Args:
            topic (str): Topic to subscribe to
            callback (Callable): Callback function to call when a message is received
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message broker"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the message broker"""
        pass

class RabbitMQBroker(MessageBroker):
    """RabbitMQ message broker implementation"""
    
    def __init__(self, host: str, port: int, username: str, password: str, logger: Optional[logging.Logger] = None):
        """
        Initialize the RabbitMQ broker
        
        Args:
            host (str): RabbitMQ host
            port (int): RabbitMQ port
            username (str): RabbitMQ username
            password (str): RabbitMQ password
            logger (logging.Logger, optional): Logger to use. Defaults to None.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.logger = logger or logging.getLogger(__name__)
        self.connection = None
        self.channel = None
        self._subscriptions = {}
    
    async def connect(self) -> None:
        """Connect to RabbitMQ"""
        try:
            # Import here to avoid dependency if not used
            import aio_pika
            
            # Connect to RabbitMQ
            self.connection = await aio_pika.connect_robust(
                host=self.host,
                port=self.port,
                login=self.username,
                password=self.password
            )
            
            # Create channel
            self.channel = await self.connection.channel()
            
            self.logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
        except ImportError:
            self.logger.error("aio_pika package not installed. Install with pip install aio-pika")
            raise
        except Exception as e:
            self.logger.error(f"Error connecting to RabbitMQ: {str(e)}")
            raise
    
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """
        Publish a message to a topic
        
        Args:
            topic (str): Topic to publish to
            message (Dict[str, Any]): Message to publish
        """
        if not self.channel:
            await self.connect()
        
        try:
            # Import here to avoid dependency if not used
            import aio_pika
            
            # Declare exchange
            exchange = await self.channel.declare_exchange(
                name=topic,
                type=aio_pika.ExchangeType.FANOUT,
                durable=True
            )
            
            # Publish message
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    content_type="application/json"
                ),
                routing_key=""
            )
            
            self.logger.debug(f"Published message to topic {topic}: {message}")
        except Exception as e:
            self.logger.error(f"Error publishing message to topic {topic}: {str(e)}")
            raise
    
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Subscribe to a topic
        
        Args:
            topic (str): Topic to subscribe to
            callback (Callable): Callback function to call when a message is received
        """
        if not self.channel:
            await self.connect()
        
        try:
            # Import here to avoid dependency if not used
            import aio_pika
            
            # Declare exchange
            exchange = await self.channel.declare_exchange(
                name=topic,
                type=aio_pika.ExchangeType.FANOUT,
                durable=True
            )
            
            # Declare queue
            queue = await self.channel.declare_queue(exclusive=True)
            
            # Bind queue to exchange
            await queue.bind(exchange)
            
            # Define message handler
            async def message_handler(message):
                async with message.process():
                    try:
                        message_body = json.loads(message.body.decode())
                        await callback(message_body)
                    except Exception as e:
                        self.logger.error(f"Error processing message from topic {topic}: {str(e)}")
            
            # Start consuming
            await queue.consume(message_handler)
            
            # Store subscription
            self._subscriptions[topic] = (exchange, queue)
            
            self.logger.info(f"Subscribed to topic {topic}")
        except Exception as e:
            self.logger.error(f"Error subscribing to topic {topic}: {str(e)}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ"""
        if self.connection:
            try:
                await self.connection.close()
                self.logger.info("Disconnected from RabbitMQ")
            except Exception as e:
                self.logger.error(f"Error disconnecting from RabbitMQ: {str(e)}")
            finally:
                self.connection = None
                self.channel = None
                self._subscriptions = {}
    
    async def is_connected(self) -> bool:
        """Check if connected to RabbitMQ"""
        return self.connection is not None and not self.connection.is_closed

def create_message_broker(broker_type: str, config: Dict[str, Any], logger: Optional[logging.Logger] = None) -> MessageBroker:
    """
    Create a message broker instance
    
    Args:
        broker_type (str): Type of message broker to create
        config (Dict[str, Any]): Configuration for the message broker
        logger (logging.Logger, optional): Logger to use. Defaults to None.
        
    Returns:
        MessageBroker: Message broker instance
    """
    if broker_type == "rabbitmq":
        return RabbitMQBroker(
            host=config.get("host", "localhost"),
            port=config.get("port", 5672),
            username=config.get("username", "guest"),
            password=config.get("password", "guest"),
            logger=logger
        )
    else:
        raise ValueError(f"Unsupported message broker type: {broker_type}") 