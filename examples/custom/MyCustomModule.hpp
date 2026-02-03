#ifndef MY_CUSTOM_MODULE_HPP
#define MY_CUSTOM_MODULE_HPP

#include <streampu.hpp>
#include <iostream>
#include <memory>
#include <array>
#include <thread>

namespace spu
{
namespace module
{
class MyCustomModule : public Stateful {

public:

    MyCustomModule(const int data_size);
    void process(int* input, int* output, const int frame_id);
    
private:
    int data_size;

};
}
}

#endif // MY_CUSTOM_MODULE_HPP
