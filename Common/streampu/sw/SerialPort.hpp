#ifndef SERIALPORT_HPP
#define SERIALPORT_HPP

#include "streampu.hpp"

#include <boost/asio.hpp>
#include <iostream>
#include <memory>
#include <array>
#include <thread>

namespace spu
{
namespace module
{

class SerialPort : public Stateful {

public:

    SerialPort(const std::string& port_name, unsigned int baud_rate, int frame_size,
               boost::asio::serial_port_base::parity::type parity           = boost::asio::serial_port_base::parity::even,
               boost::asio::serial_port_base::stop_bits::type stop_bits     = boost::asio::serial_port_base::stop_bits::one,
               boost::asio::serial_port_base::flow_control::type flow_control = boost::asio::serial_port_base::flow_control::none);
    void write(int* input, int* output, const int frame_id);
    void close();
    void run();

private:

    int frame_size;
    boost::asio::io_service io;
    boost::asio::serial_port serial;
    std::array<char, 128> read_buffer;

};
}
}

#endif // SERIALPORT_HPP
