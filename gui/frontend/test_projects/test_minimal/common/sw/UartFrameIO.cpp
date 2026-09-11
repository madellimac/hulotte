#include "UartFrameIO.hpp"

#include <boost/asio/deadline_timer.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <sstream>
#include <stdexcept>

using namespace spu;
using namespace spu::module;

UartFrameIO::UartFrameIO(const std::string& port_name,
                         unsigned int baud_rate,
                         int frame_size,
                         unsigned int read_timeout_ms,
                         boost::asio::serial_port_base::parity::type parity,
                         boost::asio::serial_port_base::stop_bits::type stop_bits,
                         boost::asio::serial_port_base::flow_control::type flow_control)
    : Stateful(), frame_size(frame_size), read_timeout_ms(read_timeout_ms), io(), serial(io, port_name)
{
    if (frame_size <= 0)
        throw tools::invalid_argument(__FILE__, __LINE__, __func__, "frame_size has to be > 0");
    if (read_timeout_ms == 0)
        throw tools::invalid_argument(__FILE__, __LINE__, __func__, "read_timeout_ms has to be > 0");

    serial.set_option(boost::asio::serial_port_base::baud_rate(baud_rate));
    serial.set_option(boost::asio::serial_port_base::character_size(8));
    serial.set_option(boost::asio::serial_port_base::parity(parity));
    serial.set_option(boost::asio::serial_port_base::stop_bits(stop_bits));
    serial.set_option(boost::asio::serial_port_base::flow_control(flow_control));

    this->set_name("UartFrameIO");
    this->set_short_name("UartFrameIO");

    auto& t = this->create_task("exchange");
    auto p_in = this->create_socket_in<int>(t, "input", frame_size);
    auto p_out = this->create_socket_out<int>(t, "output", frame_size);

    this->create_codelet(t, [p_in, p_out](Module& m, runtime::Task& t, const size_t frame_id) -> int {
        static_cast<UartFrameIO&>(m).exchange(
            static_cast<int*>(t[p_in].get_dataptr()),
            static_cast<int*>(t[p_out].get_dataptr()),
            static_cast<int>(frame_id));
        return 0;
    });
}

std::size_t UartFrameIO::read_with_timeout(uint8_t* buffer, std::size_t size)
{
    boost::system::error_code ec = boost::asio::error::would_block;
    std::size_t bytes_read = 0;

    boost::asio::deadline_timer timer(io);
    timer.expires_from_now(boost::posix_time::milliseconds(read_timeout_ms));
    timer.async_wait([&](const boost::system::error_code& timer_ec) {
        if (!timer_ec)
            serial.cancel();
    });

    boost::asio::async_read(
        serial,
        boost::asio::buffer(buffer, size),
        boost::asio::transfer_exactly(size),
        [&](const boost::system::error_code& read_ec, std::size_t n) {
            ec = read_ec;
            bytes_read = n;
        });

    io.reset();
    while (ec == boost::asio::error::would_block)
        io.run_one();

    timer.cancel();

    if (ec)
    {
        std::ostringstream oss;
        if (ec == boost::asio::error::operation_aborted)
            oss << "UART read timeout after " << read_timeout_ms << " ms (no FPGA response?)";
        else
            oss << "UART read failed: " << ec.message();

        throw std::runtime_error(oss.str());
    }

    return bytes_read;
}

void UartFrameIO::exchange(int* input, int* output, const int frame_id)
{
    (void)frame_id;

    std::vector<uint8_t> tx(static_cast<size_t>(frame_size));
    std::vector<uint8_t> rx(static_cast<size_t>(frame_size));

    for (int i = 0; i < frame_size; i++)
        tx[static_cast<size_t>(i)] = static_cast<uint8_t>(input[i] & 0xFF);

    boost::asio::write(serial, boost::asio::buffer(tx.data(), tx.size()));
    this->read_with_timeout(rx.data(), rx.size());

    for (int i = 0; i < frame_size; i++)
        output[i] = static_cast<int>(rx[static_cast<size_t>(i)]);
}

void UartFrameIO::close()
{
    if (serial.is_open())
        serial.close();
}