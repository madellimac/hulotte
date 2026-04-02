#ifndef UARTFRAMEIO_HPP
#define UARTFRAMEIO_HPP

#include "streampu.hpp"

#include <boost/asio.hpp>
#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

namespace spu
{
namespace module
{

class UartFrameIO : public Stateful
{
public:
    UartFrameIO(const std::string& port_name,
                unsigned int baud_rate,
                int frame_size,
                unsigned int read_timeout_ms = 1000,
                boost::asio::serial_port_base::parity::type parity = boost::asio::serial_port_base::parity::none,
                boost::asio::serial_port_base::stop_bits::type stop_bits = boost::asio::serial_port_base::stop_bits::one,
                boost::asio::serial_port_base::flow_control::type flow_control = boost::asio::serial_port_base::flow_control::none);

    void exchange(int* input, int* output, const int frame_id);
    void close();

private:
    std::size_t read_with_timeout(uint8_t* buffer, std::size_t size);

    int frame_size;
    unsigned int read_timeout_ms;
    boost::asio::io_service io;
    boost::asio::serial_port serial;
};

}
}

#endif // UARTFRAMEIO_HPP